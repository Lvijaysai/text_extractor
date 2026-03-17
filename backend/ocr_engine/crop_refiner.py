#backend/ocr_engine/crop_refiner.py
from difflib import SequenceMatcher

from .roi import crop_absolute_roi

LOW_CONFIDENCE_THRESHOLDS = {
    "name": 0.90,
    "father_name": 0.90,
    "dob": 0.86,
    "address": 0.82,
    "state": 0.84,
    "pin": 0.86,
}

FIELD_LABEL_TOKENS = {
    "name": {"LAST", "FIRST", "MIDDLE", "NAME", "SURNAME", "FULL"},
    "father_name": {"LAST", "FIRST", "MIDDLE", "NAME", "SURNAME", "FATHER"},
    "dob": {"DATE", "BIRTH", "DAY", "MONTH", "YEAR"},
    "address": {
        "ADDRESS",
        "RESIDENCE",
        "STATE",
        "PINCODE",
        "ZIP",
        "COUNTRY",
        "VILLAGE",
        "TOWN",
        "CITY",
        "DISTRICT",
    },
    "state": {"STATE", "UNION", "TERRITORY"},
    "pin": {"PINCODE", "ZIP", "CODE"},
}

FIELD_PADDING_PROFILES = {
    "name": {"expand_x": 0.06, "expand_y": 0.14, "shrink_x": 0.05, "shrink_y": 0.10},
    "father_name": {"expand_x": 0.06, "expand_y": 0.14, "shrink_x": 0.05, "shrink_y": 0.10},
    "dob": {"expand_x": 0.05, "expand_y": 0.18, "shrink_x": 0.04, "shrink_y": 0.10},
    "address": {"expand_x": 0.03, "expand_y": 0.07, "shrink_x": 0.03, "shrink_y": 0.06},
    "state": {"expand_x": 0.05, "expand_y": 0.16, "shrink_x": 0.04, "shrink_y": 0.10},
    "pin": {"expand_x": 0.06, "expand_y": 0.18, "shrink_x": 0.04, "shrink_y": 0.10},
}

REFINABLE_FIELDS = set(FIELD_PADDING_PROFILES)


def _normalize_text(text):
    normalized = "".join(char if char.isalnum() else " " for char in text.upper())
    return " ".join(normalized.split())


def label_leakage_score(field, raw_text):
    label_tokens = FIELD_LABEL_TOKENS.get(field)
    if not label_tokens:
        return 0.0

    raw_tokens = _normalize_text(raw_text).split()
    if not raw_tokens:
        return 0.0

    matches = 0
    for label_token in label_tokens:
        if any(
            SequenceMatcher(None, label_token, raw_token).ratio() >= 0.84
            for raw_token in raw_tokens
        ):
            matches += 1

    return matches / len(label_tokens)


def should_refine_crop(field, raw_text, clean_text, confidence):
    if field not in REFINABLE_FIELDS:
        return False

    if confidence < LOW_CONFIDENCE_THRESHOLDS[field]:
        return True

    if label_leakage_score(field, raw_text) >= 0.18:
        return True

    if raw_text.strip() and not clean_text.strip():
        return True

    return False


def _clamp_roi(roi, image_shape):
    image_h, image_w = image_shape[:2]
    x1, y1, x2, y2 = roi
    x1 = max(0, min(image_w - 1, int(round(x1))))
    y1 = max(0, min(image_h - 1, int(round(y1))))
    x2 = max(x1 + 1, min(image_w, int(round(x2))))
    y2 = max(y1 + 1, min(image_h, int(round(y2))))

    if (x2 - x1) < 12 or (y2 - y1) < 12:
        return None

    return (x1, y1, x2, y2)


def _apply_padding(base_roi, deltas, image_shape):
    x1, y1, x2, y2 = base_roi
    left_delta, top_delta, right_delta, bottom_delta = deltas
    return _clamp_roi(
        (x1 + left_delta, y1 + top_delta, x2 + right_delta, y2 + bottom_delta),
        image_shape,
    )


def _candidate_rois(field, base_roi, image_shape):
    x1, y1, x2, y2 = base_roi
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    profile = FIELD_PADDING_PROFILES[field]

    expand_x = max(4, int(width * profile["expand_x"]))
    expand_y = max(4, int(height * profile["expand_y"]))
    shrink_x = max(3, int(width * profile["shrink_x"]))
    shrink_y = max(3, int(height * profile["shrink_y"]))

    variants = (
        (0, 0, 0, 0),
        (-expand_x, 0, 0, 0),
        (0, 0, expand_x, 0),
        (0, -expand_y, 0, 0),
        (0, 0, 0, expand_y),
        (-expand_x, -expand_y, expand_x, expand_y),
        (shrink_x, 0, 0, 0),
        (0, shrink_y, 0, 0),
        (shrink_x, shrink_y, 0, 0),
        (0, 0, -shrink_x, 0),
        (0, 0, 0, -shrink_y),
        (shrink_x, 0, expand_x, 0),
        (0, shrink_y, 0, expand_y),
    )

    seen = set()
    candidates = []
    for variant in variants:
        roi = _apply_padding(base_roi, variant, image_shape)
        if roi and roi not in seen:
            seen.add(roi)
            candidates.append(roi)

    return candidates


def _roi_distance_score(roi, base_roi):
    movement = sum(abs(current - base) for current, base in zip(roi, base_roi))
    perimeter = max(
        1,
        (base_roi[2] - base_roi[0]) + (base_roi[3] - base_roi[1]),
    )
    return movement / perimeter


def _score_result(field, roi, base_roi, result):
    raw_text = result["raw_text"]
    clean_text = result["clean_text"]
    confidence = result["confidence"]
    compact_clean = clean_text.replace(" ", "")

    score = confidence
    if compact_clean:
        score += min(0.18, len(compact_clean) * 0.008)
    elif raw_text.strip():
        score -= 0.10

    score -= label_leakage_score(field, raw_text) * 0.85
    score -= _roi_distance_score(roi, base_roi) * 0.15
    return score


def refine_field_crop(field, base_roi, aligned_img, clean_img, extractor, initial_result=None):
    if field not in REFINABLE_FIELDS:
        return base_roi, initial_result

    if initial_result is None:
        initial_result = extractor(
            crop_absolute_roi(aligned_img, base_roi),
            crop_absolute_roi(clean_img, base_roi),
        )

    if not should_refine_crop(
        field,
        initial_result["raw_text"],
        initial_result["clean_text"],
        initial_result["confidence"],
    ):
        return base_roi, initial_result

    best_roi = base_roi
    best_result = initial_result
    best_score = _score_result(field, best_roi, base_roi, best_result)

    for candidate_roi in _candidate_rois(field, base_roi, aligned_img.shape):
        if candidate_roi == base_roi:
            continue

        candidate_result = extractor(
            crop_absolute_roi(aligned_img, candidate_roi),
            crop_absolute_roi(clean_img, candidate_roi),
        )
        candidate_score = _score_result(field, candidate_roi, base_roi, candidate_result)
        if candidate_score > best_score:
            best_roi = candidate_roi
            best_result = candidate_result
            best_score = candidate_score

    return best_roi, best_result
