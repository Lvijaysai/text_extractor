#backend/ocr_engine/output_fields.py
PRIMARY_OUTPUT_FIELDS = (
    "full_name",
    "dob",
    "gender",
    "father_name",
    "location",
    "address_details",
)

METADATA_OUTPUT_FIELDS = (
    "confidence_metrics",
    "raw_extracted_text",
)

DEFAULT_OUTPUT_FIELDS = PRIMARY_OUTPUT_FIELDS + METADATA_OUTPUT_FIELDS
ALLOWED_OUTPUT_FIELDS = set(DEFAULT_OUTPUT_FIELDS)

ENGINE_FIELDS = (
    "name",
    "dob",
    "gender",
    "father_name",
    "address",
    "state",
    "pin",
)

OUTPUT_TO_PUBLIC_ENGINE_FIELDS = {
    "full_name": ("name",),
    "dob": ("dob",),
    "gender": ("gender",),
    "father_name": ("father_name",),
    "location": ("state", "pin"),
    "address_details": ("address",),
}

OUTPUT_TO_REQUIRED_ENGINE_FIELDS = {
    "full_name": ("name",),
    "dob": ("dob",),
    "gender": ("gender",),
    "father_name": ("father_name",),
    "location": ("state", "pin"),
    # Address parsing is more reliable with state/pin and known-name hints.
    "address_details": ("address", "state", "pin", "name", "father_name"),
}


def ordered_unique_fields(fields, preferred_order):
    seen = set()
    ordered = []

    for field in preferred_order:
        if field in fields and field not in seen:
            ordered.append(field)
            seen.add(field)

    for field in fields:
        if field not in seen:
            ordered.append(field)
            seen.add(field)

    return tuple(ordered)


def selected_primary_fields(output_fields):
    return tuple(field for field in PRIMARY_OUTPUT_FIELDS if field in output_fields)


def has_selected_primary_fields(output_fields):
    return any(field in output_fields for field in PRIMARY_OUTPUT_FIELDS)


def public_engine_fields(output_fields):
    fields = []
    for output_field in selected_primary_fields(output_fields):
        fields.extend(OUTPUT_TO_PUBLIC_ENGINE_FIELDS[output_field])
    return ordered_unique_fields(fields, ENGINE_FIELDS)


def required_engine_fields(output_fields):
    fields = []
    for output_field in selected_primary_fields(output_fields):
        fields.extend(OUTPUT_TO_REQUIRED_ENGINE_FIELDS[output_field])
    return ordered_unique_fields(fields, ENGINE_FIELDS)


def filter_profile_payload(profile, output_fields, public_fields):
    filtered = {
        field: profile[field]
        for field in PRIMARY_OUTPUT_FIELDS
        if field in output_fields and field in profile
    }

    if "confidence_metrics" in output_fields:
        filtered["confidence_metrics"] = {
            field: value
            for field, value in profile.get("confidence_metrics", {}).items()
            if field in public_fields
        }

    if "raw_extracted_text" in output_fields:
        filtered["raw_extracted_text"] = {
            field: value
            for field, value in profile.get("raw_extracted_text", {}).items()
            if field in public_fields
        }

    return filtered
