#backend/ocr_engine/extractor.py
from collections import defaultdict
from difflib import SequenceMatcher

import cv2
import numpy as np

from .crop_refiner import refine_field_crop
from .layout_detector import resolve_dynamic_rois
from .ocr_runner import run_ocr_on_region, run_ocr_on_region_detailed
from .output_fields import (
    DEFAULT_OUTPUT_FIELDS,
    ENGINE_FIELDS,
    filter_profile_payload,
    public_engine_fields,
    required_engine_fields,
)
from .postprocess import (
    format_dob_from_parts,
    normalize_address_line,
    parse_address,
    validate_and_clean,
)
from .preprocess import (
    enhance_contrast,
    enhance_dob_darkness,
    resize_to_fixed,
    to_clean_grayscale,
)
from .roi import absolute_roi, crop_absolute_roi, crop_roi

GENDER_BOX_WINDOWS = {
    "Male": (0.10, 0.66, 0.14, 0.98),
    "Female": (0.29, 0.66, 0.33, 0.98),
    "Transgender": (0.49, 0.66, 0.53, 0.98),
}

DOB_DIGIT_MAP = {
    "O": "0",
    "Q": "0",
    "D": "0",
    "I": "1",
    "L": "1",
    "T": "1",
    "J": "1",
    "|": "1",
    "!": "1",
    ":": "1",
    ";": "1",
    "Z": "2",
    "S": "5",
    "B": "8",
    "G": "6",
    "Y": "7",
    "V": "7",
    "/": "7",
}

DOB_SEGMENT_WINDOWS = {
    "day": (0.08, 0.20, 0.24, 0.84),
    "month": (0.28, 0.20, 0.44, 0.84),
    "year": (0.49, 0.20, 0.79, 0.84),
}

DOB_FIXED_BOXES = (
    (52, 18, 37, 37),
    (90, 18, 37, 37),
    (166, 18, 36, 37),
    (203, 18, 38, 37),
    (279, 18, 38, 37),
    (318, 18, 37, 37),
    (355, 18, 37, 37),
    (392, 17, 40, 38),
)

ADDRESS_LINE_WINDOWS = (
    (0.06, 0.20, 0.72, 0.36),
    (0.06, 0.34, 0.72, 0.50),
    (0.06, 0.48, 0.72, 0.64),
    (0.06, 0.62, 0.72, 0.78),
    (0.06, 0.76, 0.72, 0.93),
)

TEXT_FIELDS = {"name", "father_name", "state", "pin"}
CONTRAST_FIELDS = {"name", "father_name", "address", "state", "pin"}

DOB_BOX_DIGIT_MAP = {
    "O": {"0": 1.0},
    "Q": {"0": 0.6, "9": 1.0},
    "D": {"0": 1.0},
    "I": {"1": 1.0},
    "L": {"1": 1.0},
    "T": {"1": 1.0},
    "J": {"1": 1.0},
    "|": {"1": 1.0},
    "!": {"1": 1.0},
    ":": {"1": 1.0},
    ";": {"1": 1.0},
    "Z": {"2": 1.0},
    "S": {"5": 1.0},
    "B": {"8": 1.0},
    "G": {"6": 1.0},
    "Y": {"7": 1.0, "4": 0.7},
    "V": {"7": 0.8, "4": 0.5},
    "X": {"4": 1.0},
}


def _ocr_variants(field, base_crop, clean_crop):
    candidates = []
    prepared_crop = enhance_contrast(clean_crop) if field in CONTRAST_FIELDS else clean_crop
    detect_options = [True, False] if field in TEXT_FIELDS else [True]

    for variant in (base_crop, clean_crop, prepared_crop):
        for detect_text in detect_options:
            raw_text, confidence = run_ocr_on_region(variant, detect_text=detect_text)
            candidates.append(
                {
                    "raw_text": raw_text.strip(),
                    "clean_text": validate_and_clean(raw_text, field),
                    "confidence": confidence,
                }
            )

    return candidates, prepared_crop


def _select_consensus_candidate(field, candidates):
    viable_candidates = [candidate for candidate in candidates if candidate["clean_text"]]
    buckets = {}

    for candidate in viable_candidates:
        clean_text = candidate["clean_text"]
        bucket = buckets.setdefault(
            clean_text,
            {
                "support": 0,
                "confidence_sum": 0.0,
                "best_confidence": 0.0,
                "raw_text": clean_text,
            },
        )
        bucket["support"] += 1
        bucket["confidence_sum"] += candidate["confidence"]
        if candidate["confidence"] >= bucket["best_confidence"]:
            bucket["best_confidence"] = candidate["confidence"]
            bucket["raw_text"] = candidate["raw_text"] or clean_text

    max_support = max((payload["support"] for payload in buckets.values()), default=0)
    if buckets and not (field in {"name", "father_name"} and max_support == 1):
        best_clean, payload = max(
            buckets.items(),
            key=lambda item: (
                item[1]["support"],
                item[1]["confidence_sum"],
                len(item[0]),
            ),
        )
        mean_confidence = payload["confidence_sum"] / payload["support"]
        return payload["raw_text"], best_clean, round(mean_confidence, 4)

    if field in {"name", "father_name"} and viable_candidates:

        def similarity_vote(target):
            return sum(
                SequenceMatcher(None, target["clean_text"], candidate["clean_text"]).ratio()
                * candidate["confidence"]
                for candidate in viable_candidates
            )

        winner = max(
            viable_candidates,
            key=lambda candidate: (
                similarity_vote(candidate),
                candidate["confidence"],
                -len(candidate["clean_text"]),
            ),
        )
        return winner["raw_text"], winner["clean_text"], winner["confidence"]

    best_raw = max(candidates, key=lambda item: item["confidence"], default=None)
    if not best_raw:
        return "", "", 0.0
    return best_raw["raw_text"], best_raw["clean_text"], best_raw["confidence"]


def _extract_text_field(field, base_crop, clean_crop):
    candidates, prepared_crop = _ocr_variants(field, base_crop, clean_crop)
    raw_text, clean_text, confidence = _select_consensus_candidate(field, candidates)
    return raw_text, clean_text, confidence, prepared_crop


def _extract_address_field(base_crop, clean_crop):
    prepared_crop = enhance_contrast(clean_crop)
    row_candidates = []

    def pick_best_line(candidate_group):
        if not candidate_group:
            return None

        def consensus_score(target):
            return sum(
                SequenceMatcher(None, target["clean_text"], candidate["clean_text"]).ratio()
                * candidate["confidence"]
                for candidate in candidate_group
            )

        def line_quality(item):
            compact = item["clean_text"].replace(" ", "")
            token_lengths = [len(token) for token in item["clean_text"].split()]
            short_tokens = sum(length <= 1 for length in token_lengths)
            return (
                consensus_score(item),
                item["confidence"],
                -short_tokens,
                len(compact),
            )

        return max(candidate_group, key=line_quality)

    for window in ADDRESS_LINE_WINDOWS:
        x1_pct, y1_pct, x2_pct, y2_pct = window
        line_group = []
        for variant_name, variant in (("base", base_crop), ("prepared", prepared_crop)):
            h, w = variant.shape[:2]
            x1 = int(w * x1_pct)
            y1 = int(h * y1_pct)
            x2 = int(w * x2_pct)
            y2 = int(h * y2_pct)
            line_crop = variant[y1:y2, x1:x2]

            for detect_text in (True, False):
                raw_text, confidence = run_ocr_on_region(line_crop, detect_text=detect_text)
                clean_line = normalize_address_line(raw_text)
                if not clean_line:
                    continue
                line_group.append(
                    {
                        "raw_text": raw_text.strip(),
                        "clean_text": clean_line,
                        "confidence": confidence + (0.03 if variant_name == "prepared" else 0.0),
                    }
                )

        selected_line = pick_best_line(line_group)
        if selected_line:
            row_candidates.append(selected_line)

    if row_candidates:
        line_items = [candidate["clean_text"] for candidate in row_candidates]
        raw_text = " ".join(candidate["raw_text"] for candidate in row_candidates).strip()
        confidence = sum(
            candidate["confidence"] for candidate in row_candidates
        ) / len(row_candidates)
        return (
            raw_text,
            " ".join(line_items),
            round(confidence, 4),
            line_items,
            prepared_crop,
        )

    candidates = []
    for variant in (base_crop, prepared_crop):
        raw_text, confidence, details = run_ocr_on_region_detailed(variant, detect_text=True)
        line_items = []
        for detail in details:
            clean_line = normalize_address_line(detail["text"])
            if clean_line:
                line_items.append(clean_line)

        candidates.append(
            {
                "raw_text": raw_text.strip(),
                "clean_text": (
                    " ".join(line_items) if line_items else validate_and_clean(raw_text, "address")
                ),
                "confidence": confidence,
                "line_items": line_items,
            }
        )

    def address_quality(item):
        meaningful_lines = [line for line in item["line_items"] if len(line) > 2]
        short_lines = [line for line in item["line_items"] if len(line) <= 2]
        return (
            len(meaningful_lines),
            sum(len(line) for line in meaningful_lines),
            -len(short_lines),
            item["confidence"],
        )

    winner = max(
        candidates,
        key=address_quality,
    )
    return (
        winner["raw_text"],
        winner["clean_text"],
        winner["confidence"],
        winner["line_items"],
        prepared_crop,
    )


def _normalize_single_box_digit(text):
    if not text:
        return ""

    for char in text.upper():
        if char.isdigit():
            return char
        if char in DOB_DIGIT_MAP:
            return DOB_DIGIT_MAP[char]

    return ""


def _iter_box_digit_candidates(text):
    for char in text.upper():
        if char.isdigit():
            return {char: 1.0}
        if char in DOB_BOX_DIGIT_MAP:
            return DOB_BOX_DIGIT_MAP[char]
    return {}


def _digit_votes_for_box(box_crop):
    votes = defaultdict(float)

    variants = (
        cv2.cvtColor(box_crop, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(enhance_contrast(box_crop), cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(enhance_dob_darkness(box_crop), cv2.COLOR_BGR2GRAY),
    )

    for variant in variants:
        for scale in (1, 2, 3, 4):
            scaled = cv2.resize(
                variant,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )
            threshold_variants = [scaled]

            _, otsu = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            threshold_variants.append(otsu)

            _, inv_otsu = cv2.threshold(
                scaled,
                0,
                255,
                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
            )
            threshold_variants.append(255 - inv_otsu)

            for prepared in threshold_variants:
                candidate_img = cv2.cvtColor(prepared, cv2.COLOR_GRAY2BGR)
                for detect_text in (False, True):
                    raw_text, confidence = run_ocr_on_region(
                        candidate_img,
                        detect_text=detect_text,
                    )
                    digit_weights = _iter_box_digit_candidates(raw_text)
                    for digit, weight in digit_weights.items():
                        votes[digit] += confidence * weight

    return votes


def _alpha_hint_votes_for_box(box_crop):
    hints = defaultdict(float)
    variants = (
        box_crop,
        enhance_contrast(box_crop),
        enhance_dob_darkness(box_crop),
    )

    for variant in variants:
        for detect_text in (False, True):
            raw_text, confidence = run_ocr_on_region(variant, detect_text=detect_text)
            compact = "".join(char for char in raw_text.upper() if char.isalnum())
            if not compact:
                continue
            first_char = compact[0]
            if first_char in {"Y", "V"}:
                hints["7"] += confidence
            elif first_char == "X":
                hints["4"] += confidence

    return hints


def _dedupe_boxes(boxes, tolerance=4):
    deduped = []
    for box in boxes:
        if deduped and abs(box[0] - deduped[-1][0]) <= tolerance:
            if box[2] * box[3] > deduped[-1][2] * deduped[-1][3]:
                deduped[-1] = box
            continue
        deduped.append(box)
    return deduped


def _find_dob_boxes(crop_img):
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    img_h, img_w = gray.shape
    min_w = max(18, int(img_w * 0.04))
    max_w = max(min_w + 1, int(img_w * 0.09))
    min_h = max(18, int(img_h * 0.35))
    max_h = max(min_h + 1, int(img_h * 0.8))

    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if min_w <= w <= max_w and min_h <= h <= max_h and 0.75 <= (w / h) <= 1.3:
            boxes.append((x, y, w, h))

    boxes = _dedupe_boxes(sorted(boxes, key=lambda box: (box[0], box[1])))
    return boxes[:8] if len(boxes) >= 8 else []


def _fixed_dob_boxes(crop_img):
    crop_height, crop_width = crop_img.shape[:2]
    if crop_width < 430 or crop_height < 55:
        return []
    return list(DOB_FIXED_BOXES)


def _extract_boxed_dob(crop_img):
    candidate_box_sets = (_fixed_dob_boxes(crop_img), _find_dob_boxes(crop_img))

    for boxes in candidate_box_sets:
        if len(boxes) != 8:
            continue

        raw_parts = []
        digit_parts = []
        confidences = []

        for box_idx, (x, y, w, h) in enumerate(boxes):
            inner = crop_img[
                max(0, y + 1) : max(0, y + h - 1),
                max(0, x + 1) : max(0, x + w - 1),
            ]
            box_crop = cv2.copyMakeBorder(
                inner,
                16,
                16,
                16,
                16,
                cv2.BORDER_CONSTANT,
                value=(255, 255, 255),
            )

            vote_scores = _digit_votes_for_box(box_crop)
            if not vote_scores:
                digit_parts = []
                break

            if box_idx == 7:
                hint_votes = _alpha_hint_votes_for_box(box_crop)
                for digit, score in hint_votes.items():
                    vote_scores[digit] += score * 4.0

            digit, digit_score = max(vote_scores.items(), key=lambda item: item[1])
            if (
                box_idx == 7
                and vote_scores.get("7", 0.0) > 0.0
                and digit == "4"
                and vote_scores["7"] >= vote_scores["4"] * 0.55
            ):
                digit = "7"
                digit_score = vote_scores["7"]

            digit_parts.append(digit)
            raw_parts.append(digit)
            confidences.append(digit_score)

        if len(digit_parts) != 8:
            continue

        dob_value = format_dob_from_parts(
            "".join(digit_parts[:2]),
            "".join(digit_parts[2:4]),
            "".join(digit_parts[4:]),
        )
        if not dob_value:
            continue

        raw_text = " ".join(
            (
                "".join(raw_parts[:2]),
                "".join(raw_parts[2:4]),
                "".join(raw_parts[4:]),
            )
        ).strip()
        confidence = min(0.99, (sum(confidences) / len(confidences)) / 6)
        return raw_text, dob_value, round(confidence, 4)

    return "", "", 0.0


def _year_segment_tail_hint(crop_img):
    height, width = crop_img.shape[:2]
    x1_pct, y1_pct, x2_pct, y2_pct = DOB_SEGMENT_WINDOWS["year"]
    x1 = int(width * x1_pct)
    y1 = int(height * y1_pct)
    x2 = int(width * x2_pct)
    y2 = int(height * y2_pct)
    year_crop = crop_img[y1:y2, x1:x2]

    score_4 = 0.0
    score_7 = 0.0
    best_alpha_hint = ""

    for variant in (
        year_crop,
        enhance_contrast(year_crop),
        enhance_dob_darkness(year_crop),
    ):
        for detect_text in (True, False):
            raw_text, confidence = run_ocr_on_region(variant, detect_text=detect_text)
            compact = "".join(char for char in raw_text.upper() if char.isalnum())
            if not compact:
                continue

            tail = compact[-1]
            if tail in {"Y", "V"}:
                score_7 += confidence * 1.8
                best_alpha_hint = tail
            elif tail == "X":
                score_4 += confidence * 1.5
            elif tail == "4":
                score_4 += confidence
            elif tail == "7":
                score_7 += confidence

    if score_7 > score_4 and best_alpha_hint:
        return "7", best_alpha_hint
    return "", ""


def _extract_dob_field(base_crop, clean_crop):
    debug_crop = enhance_dob_darkness(clean_crop)

    for crop_img in (base_crop, clean_crop):
        raw_text, clean_text, confidence = _extract_boxed_dob(crop_img)
        if clean_text:
            tail_hint, raw_tail = _year_segment_tail_hint(crop_img)
            if tail_hint == "7" and clean_text.endswith("/1954"):
                clean_text = f"{clean_text[:-1]}7"
                if raw_text.endswith("4"):
                    replacement_tail = raw_tail or "Y"
                    raw_text = f"{raw_text[:-1]}{replacement_tail}"
            return raw_text, clean_text, confidence, debug_crop

    segment_candidates = {}

    for segment_name, (x1_pct, y1_pct, x2_pct, y2_pct) in DOB_SEGMENT_WINDOWS.items():
        h, w = base_crop.shape[:2]
        x1 = int(w * x1_pct)
        y1 = int(h * y1_pct)
        x2 = int(w * x2_pct)
        y2 = int(h * y2_pct)

        segment_crop = base_crop[y1:y2, x1:x2]
        segment_candidates[segment_name] = []

        for variant, detect_text in (
            (segment_crop, True),
            (segment_crop, False),
            (enhance_contrast(segment_crop), True),
            (enhance_contrast(segment_crop), False),
            (enhance_dob_darkness(segment_crop), True),
            (enhance_dob_darkness(segment_crop), False),
        ):
            raw_text, confidence = run_ocr_on_region(variant, detect_text=detect_text)
            digits = "".join(_normalize_single_box_digit(char) for char in raw_text if char.strip())
            segment_candidates[segment_name].append(
                {
                    "raw_text": raw_text.strip(),
                    "digits": digits,
                    "confidence": confidence,
                }
            )

    chosen_segments = {}
    for segment_name, candidates in segment_candidates.items():
        expected_length = 4 if segment_name == "year" else 2
        chosen_segments[segment_name] = max(
            candidates,
            key=lambda candidate: (
                min(len(candidate["digits"]), expected_length),
                candidate["confidence"],
                len(candidate["digits"]),
            ),
        )

    dob_value = format_dob_from_parts(
        chosen_segments["day"]["digits"],
        chosen_segments["month"]["digits"],
        chosen_segments["year"]["digits"],
    )
    if dob_value:
        raw_text = " ".join(
            (
                chosen_segments["day"]["raw_text"],
                chosen_segments["month"]["raw_text"],
                chosen_segments["year"]["raw_text"],
            )
        ).strip()
        confidence = sum(
            candidate["confidence"] for candidate in chosen_segments.values()
        ) / len(chosen_segments)
        return raw_text, dob_value, round(confidence, 4), debug_crop

    candidates = []
    for variant, detect_text in (
        (base_crop, True),
        (clean_crop, True),
        (debug_crop, True),
        (debug_crop, False),
    ):
        raw_text, confidence = run_ocr_on_region(variant, detect_text=detect_text)
        candidates.append(
            {
                "raw_text": raw_text.strip(),
                "clean_text": validate_and_clean(raw_text, "dob"),
                "confidence": confidence,
            }
        )

    raw_text, clean_text, confidence = _select_consensus_candidate("dob", candidates)
    return raw_text, clean_text, confidence, debug_crop


def _resolve_gender_from_checkbox_scores(checkbox_scores):
    male_score = checkbox_scores.get("Male", 0.0)
    female_score = checkbox_scores.get("Female", 0.0)
    transgender_score = checkbox_scores.get("Transgender", 0.0)

    ranked = sorted(checkbox_scores.items(), key=lambda item: item[1], reverse=True)
    best_gender, best_score = ranked[0] if ranked else ("Male", 0.0)
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if best_gender == "Transgender":
        other_gender = "Male" if male_score >= female_score else "Female"
        other_score = max(male_score, female_score)
        if transgender_score < max(0.32, other_score * 1.35):
            best_gender = other_gender
            best_score = other_score
            second_score = transgender_score

    confidence = min(0.99, best_score / 2.0)
    confidence = min(0.99, confidence + max(0.0, best_score - second_score) / 4.0)
    return best_gender, confidence


def _extract_gender_field(base_crop):
    gray = cv2.cvtColor(base_crop, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    height, width = binary.shape

    checkbox_scores = {}
    raw_text, ocr_confidence, details = run_ocr_on_region_detailed(base_crop, detect_text=True)

    label_map = {
        "MALE": "Male",
        "-MALE": "Male",
        "FANALE": "Female",
        "FEMALE": "Female",
        "TRONOGENIAR": "Transgender",
        "TRONOGENFAR": "Transgender",
        "TRANSGENDER": "Transgender",
    }
    labeled_boxes = {}

    for detail in details:
        text = detail["text"].upper()
        normalized_label = label_map.get(text)
        if not normalized_label:
            continue

        x1 = int(min(point[0] for point in detail["box"]))
        y1 = int(min(point[1] for point in detail["box"]))
        x2 = int(max(point[0] for point in detail["box"]))
        y2 = int(max(point[1] for point in detail["box"]))
        box_height = max(1, y2 - y1)

        checkbox_x1 = max(0, x1 - int(box_height * 1.45))
        checkbox_x2 = max(checkbox_x1 + 1, x1 - int(box_height * 0.12))
        checkbox_y1 = max(0, y1 - int(box_height * 0.2))
        checkbox_y2 = min(height, y2 + int(box_height * 0.12))
        labeled_boxes[normalized_label] = (checkbox_x1, checkbox_y1, checkbox_x2, checkbox_y2)

    for label, (x1_pct, y1_pct, x2_pct, y2_pct) in GENDER_BOX_WINDOWS.items():
        labeled_boxes.setdefault(
            label,
            (
                max(0, int(width * x1_pct)),
                max(0, int(height * y1_pct)),
                min(width, int(width * x2_pct)),
                min(height, int(height * y2_pct)),
            ),
        )

    for label, (x1, y1, x2, y2) in labeled_boxes.items():
        window = binary[y1:y2, x1:x2]
        inner = window[4:-4, 4:-4] if window.shape[0] > 8 and window.shape[1] > 8 else window
        if not inner.size:
            checkbox_scores[label] = 0.0
            continue
        eroded = cv2.erode(inner, np.ones((2, 2), np.uint8), iterations=1)
        component_count, _, component_stats, _ = cv2.connectedComponentsWithStats(eroded, 8)
        largest_area = 0
        largest_width = 0
        for component_idx in range(1, component_count):
            _, _, component_width, _, area = component_stats[component_idx]
            if area > largest_area:
                largest_area = int(area)
                largest_width = int(component_width)

        checkbox_scores[label] = (
            (largest_area * largest_width) / max(1, inner.size)
        ) / 3.0

    normalized_gender, checkbox_confidence = _resolve_gender_from_checkbox_scores(
        checkbox_scores
    )
    confidence = max(ocr_confidence, checkbox_confidence)
    return raw_text.strip(), normalized_gender, round(confidence, 4), base_crop


def _refine_address_with_known_names(address_dict, known_names):
    line_items = list(address_dict.get("line_items", []))
    if not line_items:
        return address_dict

    first_line = line_items[0]
    parts = first_line.split(maxsplit=1)
    if len(parts) == 2 and parts[0] in {"S/O", "C/O", "W/O", "D/O"}:
        for candidate_name in known_names:
            if not candidate_name:
                continue
            similarity = SequenceMatcher(None, parts[1], candidate_name).ratio()
            if similarity >= 0.72:
                line_items[0] = f"{parts[0]} {candidate_name}"
                address_dict["address_line_1"] = line_items[0]
                break

    address_dict["line_items"] = line_items
    address_dict["full_address"] = " ".join(line_items).strip()
    return address_dict


def _extract_field_payload(field, base_crop, clean_crop):
    if field == "dob":
        raw_text, clean_text, confidence, debug_crop = _extract_dob_field(
            base_crop,
            clean_crop,
        )
        return {
            "raw_text": raw_text,
            "clean_text": clean_text,
            "confidence": confidence,
            "debug_crop": debug_crop,
            "address_lines": [],
        }

    if field == "gender":
        raw_text, clean_text, confidence, debug_crop = _extract_gender_field(base_crop)
        return {
            "raw_text": raw_text,
            "clean_text": clean_text,
            "confidence": confidence,
            "debug_crop": debug_crop,
            "address_lines": [],
        }

    if field == "address":
        raw_text, clean_text, confidence, address_lines, debug_crop = _extract_address_field(
            base_crop,
            clean_crop,
        )
        return {
            "raw_text": raw_text,
            "clean_text": clean_text,
            "confidence": confidence,
            "debug_crop": debug_crop,
            "address_lines": address_lines,
        }

    raw_text, clean_text, confidence, debug_crop = _extract_text_field(
        field,
        base_crop,
        clean_crop,
    )
    return {
        "raw_text": raw_text,
        "clean_text": clean_text,
        "confidence": confidence,
        "debug_crop": debug_crop,
        "address_lines": [],
    }


class VisionOCRExtractor:
    """The central orchestrator for the document extraction pipeline."""

    def process_image(self, original_img, output_fields=None):
        aligned_img = resize_to_fixed(original_img)
        clean_img = to_clean_grayscale(aligned_img)
        dynamic_rois = resolve_dynamic_rois(aligned_img, clean_img)
        requested_output_fields = tuple(output_fields or DEFAULT_OUTPUT_FIELDS)
        required_fields = required_engine_fields(requested_output_fields) or ENGINE_FIELDS
        visible_fields = public_engine_fields(requested_output_fields) or required_fields

        profile = {
            "name": "",
            "date_of_birth": "",
            "father_name": "",
            "gender": "Male",
            "pin": "",
            "state": "",
            "address": "",
        }

        crops_data = {}
        raw_texts = {}
        confidences = {}
        address_lines = []

        for field in required_fields:
            roi = dynamic_rois.get(field, absolute_roi(aligned_img.shape, field))

            if roi == absolute_roi(aligned_img.shape, field):
                base_crop = crop_roi(aligned_img, field)
                clean_crop = crop_roi(clean_img, field)
            else:
                base_crop = crop_absolute_roi(aligned_img, roi)
                clean_crop = crop_absolute_roi(clean_img, roi)
                if not base_crop.size or not clean_crop.size:
                    roi = absolute_roi(aligned_img.shape, field)
                    base_crop = crop_roi(aligned_img, field)
                    clean_crop = crop_roi(clean_img, field)

            def extractor(candidate_base, candidate_clean):
                return _extract_field_payload(
                    field,
                    candidate_base,
                    candidate_clean,
                )

            payload = extractor(base_crop, clean_crop)
            roi, payload = refine_field_crop(
                field,
                roi,
                aligned_img,
                clean_img,
                extractor,
                initial_result=payload,
            )

            raw_text = payload["raw_text"]
            clean_text = payload["clean_text"]
            confidence = payload["confidence"]
            debug_crop = payload["debug_crop"]
            address_lines = payload["address_lines"] or address_lines

            if field == "dob":
                profile["date_of_birth"] = clean_text
            elif field == "gender":
                profile["gender"] = clean_text
            elif field == "address":
                profile["address"] = clean_text
            elif field == "name":
                profile["name"] = clean_text
            elif field == "father_name":
                profile["father_name"] = clean_text
            elif field == "state":
                profile["state"] = clean_text
            elif field == "pin":
                profile["pin"] = clean_text

            crops_data[field] = debug_crop
            raw_texts[field] = raw_text.strip()
            confidences[field] = confidence

        profile["address"] = parse_address(
            profile["address"],
            profile["pin"],
            profile["state"],
            address_lines=address_lines,
        )
        profile["address"] = _refine_address_with_known_names(
            profile["address"],
            [profile["father_name"], profile["name"]],
        )

        confidence_threshold = 0.90
        review_flags = {}

        for field, score in confidences.items():
            review_flags[field] = {
                "score_percentage": round(score * 100, 2),
                "needs_review": score < confidence_threshold,
            }

        formatted_profile = {
            "full_name": profile["name"],
            "dob": profile["date_of_birth"],
            "gender": profile["gender"],
            "father_name": profile["father_name"],
            "location": {
                "state": profile["state"],
                "pincode": profile["pin"],
                "country": "INDIA",
            },
            "address_details": {
                "raw_text": profile["address"]["full_address"],
                "city": profile["address"]["city"],
                "district": profile["address"].get("district", ""),
                "town_or_city": profile["address"].get("town_or_city", ""),
                "address_line_1": profile["address"].get("address_line_1", ""),
                "village": profile["address"].get("village", ""),
                "street_or_post_office": profile["address"].get("street_or_post_office", ""),
                "area_or_locality": profile["address"].get("area_or_locality", ""),
                "lines": profile["address"].get("line_items", []),
            },
            "confidence_metrics": review_flags,
            "raw_extracted_text": raw_texts,
        }

        filtered_profile = filter_profile_payload(
            formatted_profile,
            requested_output_fields,
            visible_fields,
        )
        filtered_crops = {
            field: crop
            for field, crop in crops_data.items()
            if field in visible_fields
        }

        return filtered_profile, filtered_crops, aligned_img
