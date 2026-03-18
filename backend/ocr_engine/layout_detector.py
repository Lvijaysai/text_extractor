#backend/ocr_engine/layout_detector.py
from difflib import SequenceMatcher

import numpy as np

from .ocr_runner import run_ocr_on_region_detailed
from .roi import ROIS

ANCHOR_NORMALIZATION_MAP = str.maketrans(
    {
        "0": "O",
        "1": "I",
        "5": "S",
        "6": "G",
        "8": "B",
        "$": "S",
    }
)

ANCHOR_SPECS = {
    "name": {
        "phrases": ("LAST NAME SURNAME",),
        "expected_y": 0.298,
        "threshold": 0.82,
        "tolerance": 0.07,
        "max_x_pct": 0.30,
        "max_tokens": 5,
    },
    "gender": {
        "phrases": ("GENDER",),
        "expected_y": 0.490,
        "threshold": 0.84,
        "tolerance": 0.06,
        "max_x_pct": 0.35,
        "max_tokens": 3,
    },
    "dob": {
        "phrases": ("DATE OF BIRTH",),
        "expected_y": 0.545,
        "threshold": 0.74,
        "tolerance": 0.07,
        "max_x_pct": 0.40,
        "max_tokens": 8,
    },
    "father_name": {
        "phrases": ("LAST NAME SURNAME",),
        "expected_y": 0.632,
        "threshold": 0.82,
        "tolerance": 0.08,
        "max_x_pct": 0.30,
        "max_tokens": 5,
    },
    "address": {
        "phrases": ("RESIDENCE ADDRESS", "ADDRESS"),
        "expected_y": 0.804,
        "threshold": 0.80,
        "tolerance": 0.06,
        "max_x_pct": 0.35,
        "max_tokens": 4,
    },
    "state_pin": {
        "phrases": ("STATE UNION TERRITORY", "PINCODE ZIP CODE", "PIN CODE ZIP CODE"),
        "expected_y": 0.954,
        "threshold": 0.76,
        "tolerance": 0.04,
        "max_x_pct": 0.65,
        "max_tokens": 10,
    },
}

CORE_ANCHORS = ("gender", "dob", "address", "state_pin")
FIELD_ORDER = ("name", "gender", "dob", "father_name", "address", "state", "pin")


def _normalize_anchor_text(text):
    normalized = text.upper().translate(ANCHOR_NORMALIZATION_MAP)
    normalized = "".join(char if char.isalnum() else " " for char in normalized)
    return " ".join(normalized.split())


def _box_bounds(box):
    pts = np.array(box)
    return int(pts[:, 0].min()), int(pts[:, 1].min()), int(pts[:, 0].max()), int(pts[:, 1].max())

def _anchor_phrase_score(text, phrase):
    normalized_text = _normalize_anchor_text(text)
    normalized_phrase = _normalize_anchor_text(phrase)
    if not normalized_text or not normalized_phrase:
        return 0.0

    row_tokens = normalized_text.split()
    phrase_tokens = normalized_phrase.split()
    if not row_tokens or not phrase_tokens:
        return 0.0

    token_scores = []
    for phrase_token in phrase_tokens:
        best_token_score = max(
            SequenceMatcher(None, phrase_token, row_token).ratio()
            for row_token in row_tokens
        )
        token_scores.append(best_token_score)

    average_token_score = sum(token_scores) / len(token_scores)
    token_coverage = sum(score >= 0.78 for score in token_scores) / len(token_scores)

    phrase_window_size = min(len(row_tokens), len(phrase_tokens))
    window_score = 0.0
    for start_idx in range(len(row_tokens) - phrase_window_size + 1):
        token_window = " ".join(row_tokens[start_idx : start_idx + phrase_window_size])
        window_score = max(
            window_score,
            SequenceMatcher(None, normalized_phrase, token_window).ratio(),
        )

    extra_tokens = max(0, len(row_tokens) - len(phrase_tokens))
    length_penalty = max(0.55, 1.0 - (extra_tokens * 0.08))
    base_score = max(window_score, (average_token_score * 0.6) + (token_coverage * 0.4))
    return base_score * length_penalty


def _group_ocr_rows(details, image_shape):
    image_h = image_shape[0]
    row_tolerance = max(10, int(image_h * 0.008))
    items = []

    for detail in details:
        box = detail.get("box")
        if not box:
            continue

        text = detail.get("text", "").strip()
        normalized_text = _normalize_anchor_text(text)
        if not normalized_text:
            continue

        x1, y1, x2, y2 = _box_bounds(box)
        items.append(
            {
                "text": text,
                "normalized_text": normalized_text,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "cy": (y1 + y2) / 2.0,
            }
        )

    items.sort(key=lambda item: (item["cy"], item["x1"]))
    grouped = []

    for item in items:
        if not grouped:
            grouped.append({"items": [item], "cy": item["cy"], "y1": item["y1"], "y2": item["y2"]})
            continue

        current = grouped[-1]
        if abs(item["cy"] - current["cy"]) <= row_tolerance:
            current["items"].append(item)
            current["y1"] = min(current["y1"], item["y1"])
            current["y2"] = max(current["y2"], item["y2"])
            current["cy"] = (current["y1"] + current["y2"]) / 2.0
            continue

        grouped.append({"items": [item], "cy": item["cy"], "y1": item["y1"], "y2": item["y2"]})

    rows = []
    for row in grouped:
        row_items = sorted(row["items"], key=lambda item: item["x1"])
        rows.append(
            {
                "text": " ".join(item["text"] for item in row_items),
                "normalized_text": " ".join(item["normalized_text"] for item in row_items),
                "x1": min(item["x1"] for item in row_items),
                "y1": min(item["y1"] for item in row_items),
                "x2": max(item["x2"] for item in row_items),
                "y2": max(item["y2"] for item in row_items),
                "cy": row["cy"],
                "token_count": len(
                    " ".join(item["normalized_text"] for item in row_items).split()
                ),
            }
        )

    return rows


def _select_anchor_row(rows, image_shape, spec):
    image_h, image_w = image_shape[:2]
    expected_y = spec["expected_y"]
    max_x = image_w * spec["max_x_pct"]
    tolerance = spec["tolerance"]
    max_tokens = spec["max_tokens"]
    candidates = []

    for row in rows:
        if row["x1"] > max_x:
            continue
        if row["token_count"] > max_tokens:
            continue

        text_score = max(
            _anchor_phrase_score(row["normalized_text"], phrase)
            for phrase in spec["phrases"]
        )
        if text_score < spec["threshold"]:
            continue

        y_distance = abs((row["cy"] / image_h) - expected_y)
        if y_distance > tolerance:
            continue

        position_score = 1.0 - (y_distance / tolerance)
        final_score = (text_score * 0.84) + (position_score * 0.16)
        candidates.append((final_score, row))

    if not candidates:
        return None

    return max(candidates, key=lambda item: item[0])[1]


def _collect_anchor_rows(details, image_shape):
    rows = _group_ocr_rows(details, image_shape)
    return {
        anchor_name: _select_anchor_row(rows, image_shape, spec)
        for anchor_name, spec in ANCHOR_SPECS.items()
    }


def _fit_vertical_transform(anchor_rows, image_shape):
    image_h = image_shape[0]
    anchor_pairs = []

    for anchor_name, row in anchor_rows.items():
        if not row:
            continue
        anchor_pairs.append((ANCHOR_SPECS[anchor_name]["expected_y"] * image_h, row["cy"]))

    if len(anchor_pairs) < 3:
        return None

    core_anchor_count = sum(
        1 for anchor_name in CORE_ANCHORS if anchor_rows.get(anchor_name) is not None
    )
    if core_anchor_count < 2:
        return None

    if anchor_rows.get("address") is None and anchor_rows.get("state_pin") is None:
        return None

    expected = np.array([pair[0] for pair in anchor_pairs], dtype=np.float32)
    detected = np.array([pair[1] for pair in anchor_pairs], dtype=np.float32)
    scale, offset = np.polyfit(expected, detected, 1)

    if not 0.94 <= scale <= 1.06:
        return None

    residuals = np.abs((expected * scale) + offset - detected)
    if float(np.max(residuals, initial=0.0)) > (image_h * 0.018):
        return None

    return float(scale), float(offset)


def _transform_roi(image_shape, field, scale, offset):
    image_h, image_w = image_shape[:2]
    x1_pct, y1_pct, x2_pct, y2_pct = ROIS[field]

    x1 = int(image_w * x1_pct)
    x2 = int(image_w * x2_pct)
    y1 = int(round((image_h * y1_pct * scale) + offset))
    y2 = int(round((image_h * y2_pct * scale) + offset))

    y1 = max(0, min(image_h - 2, y1))
    y2 = max(y1 + 1, min(image_h, y2))

    if (y2 - y1) < 12:
        return None

    return (x1, y1, x2, y2)


def _rois_are_ordered(dynamic_rois):
    ordered_fields = [field for field in FIELD_ORDER if field in dynamic_rois]
    y_positions = [dynamic_rois[field][1] for field in ordered_fields]
    return y_positions == sorted(y_positions)


def build_dynamic_rois_from_details(details, image_shape):
    anchor_rows = _collect_anchor_rows(details, image_shape)
    transform = _fit_vertical_transform(anchor_rows, image_shape)
    if not transform:
        return {}

    scale, offset = transform
    dynamic_rois = {}

    for field in ROIS:
        roi = _transform_roi(image_shape, field, scale, offset)
        if roi:
            dynamic_rois[field] = roi

    if len(dynamic_rois) != len(ROIS):
        return {}

    if not _rois_are_ordered(dynamic_rois):
        return {}

    return dynamic_rois


def resolve_dynamic_rois(base_img, clean_img):
    best_rois = {}

    for variant in (clean_img, base_img):
        _, _, details = run_ocr_on_region_detailed(variant, detect_text=True)
        candidate_rois = build_dynamic_rois_from_details(details, variant.shape)
        if len(candidate_rois) > len(best_rois):
            best_rois = candidate_rois

    return best_rois
