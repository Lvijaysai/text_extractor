# backend/ocr_engine/postprocess.py
import re
from datetime import date
from difflib import SequenceMatcher

INDIAN_STATES_AND_UTS = (
    "ANDAMAN AND NICOBAR ISLANDS",
    "ANDHRA PRADESH",
    "ARUNACHAL PRADESH",
    "ASSAM",
    "BIHAR",
    "CHANDIGARH",
    "CHHATTISGARH",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "DELHI",
    "GOA",
    "GUJARAT",
    "HARYANA",
    "HIMACHAL PRADESH",
    "JAMMU AND KASHMIR",
    "JHARKHAND",
    "KARNATAKA",
    "KERALA",
    "LADAKH",
    "LAKSHADWEEP",
    "MADHYA PRADESH",
    "MAHARASHTRA",
    "MANIPUR",
    "MEGHALAYA",
    "MIZORAM",
    "NAGALAND",
    "ODISHA",
    "PUDUCHERRY",
    "PUNJAB",
    "RAJASTHAN",
    "SIKKIM",
    "TAMIL NADU",
    "TELANGANA",
    "TRIPURA",
    "UTTAR PRADESH",
    "UTTARAKHAND",
    "WEST BENGAL",
)

LETTER_LIKE_DIGITS = str.maketrans(
    {
        "0": "O",
        "1": "I",
        "2": "Z",
        "5": "S",
        "6": "G",
        "8": "B",
    }
)

DIGIT_LIKE_LETTERS = {
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

ADDRESS_RELATION_PREFIXES = {"SO", "S0", "S O", "C0", "CO", "C O", "WO", "W O", "D0", "DO"}


def _collapse_spaced_letters(text):
    """Merges box-separated letters back into whole words (G A N G -> GANG)"""
    clean = text
    while re.search(r"\b([A-Z0-9])\s+([A-Z0-9])\b", clean):
        clean = re.sub(r"\b([A-Z0-9])\s+([A-Z0-9])\b", r"\1\2", clean)
    return clean


def _normalize_alpha_noise(text):
    return text.translate(LETTER_LIKE_DIGITS)


def _fuzzy_match_choice(text, choices, min_ratio=0.78):
    compact_text = re.sub(r"[\s\-]+", "", text)
    best_choice = text
    best_ratio = 0.0

    for choice in choices:
        ratio = SequenceMatcher(
            None,
            compact_text,
            re.sub(r"[\s\-]+", "", choice),
        ).ratio()
        if ratio > best_ratio:
            best_choice = choice
            best_ratio = ratio

    if best_ratio >= min_ratio:
        return best_choice
    return text


def _normalize_digit_text(text):
    DIGIT_TRANSLATION = str.maketrans(DIGIT_LIKE_LETTERS)
    # Translates characters, then strips out anything that isn't a digit (\D)
    return re.sub(r"\D", "", text.upper().translate(DIGIT_TRANSLATION))

def _pin_token_to_digits(token, include_weak_ones=False):
    strong_map = {
        "O": "0",
        "Q": "0",
        "D": "0",
        "S": "5",
        "Z": "2",
        "B": "8",
        "G": "6",
    }
    weak_one_map = {
        "I": "1",
        "L": "1",
        "T": "1",
        "J": "1",
        "|": "1",
        "!": "1",
    }

    mapped_digits = []
    char_map = dict(strong_map)
    if include_weak_ones:
        char_map.update(weak_one_map)

    for char in token:
        if char.isdigit():
            mapped_digits.append(char)
        elif char in char_map:
            mapped_digits.append(char_map[char])

    return "".join(mapped_digits)


def _extract_pin_digits(text):
    compact = re.sub(r"[^A-Z0-9|!]", "", text.upper())
    separator_chars = {"I", "L", "|", "!"}

    if len(compact) >= 10:
        even_lane = compact[::2]
        odd_lane = compact[1::2]
        even_ratio = sum(char in separator_chars for char in even_lane) / len(even_lane)
        odd_ratio = sum(char in separator_chars for char in odd_lane) / len(odd_lane)

        if even_ratio >= 0.6 and len(odd_lane) >= 6:
            digits = _pin_token_to_digits(odd_lane, include_weak_ones=True)
            if len(digits) >= 6:
                return digits[:6]

        if odd_ratio >= 0.6 and len(even_lane) >= 6:
            digits = _pin_token_to_digits(even_lane, include_weak_ones=True)
            if len(digits) >= 6:
                return digits[:6]

    for token in re.findall(r"[A-Z0-9|!]+", text.upper()):
        for include_weak_ones in (False, True):
            digits = _pin_token_to_digits(token, include_weak_ones=include_weak_ones)
            if len(digits) == 6:
                return digits
            if len(digits) > 6 and token.isdigit():
                return digits[:6]

    joined_numeric = "".join(char for char in text if char.isdigit())
    if len(joined_numeric) >= 6:
        return joined_numeric[:6]

    return ""


def _normalize_year_digits(year_digits, current_year=None):
    if not year_digits:
        return ""

    if current_year is None:
        current_year = date.today().year

    if len(year_digits) >= 4:
        candidate = year_digits[:4]
        if 1900 <= int(candidate) <= current_year:
            return candidate
        if candidate[0] in {"1", "2"} and len(candidate[-2:]) == 2:
            suffix = int(candidate[-2:])
            inferred_year = 2000 + suffix if suffix <= current_year % 100 else 1900 + suffix
            return str(inferred_year)

    if len(year_digits) == 3 and year_digits[0] in {"1", "2"}:
        suffix = int(year_digits[-2:])
        inferred_year = 2000 + suffix if suffix <= current_year % 100 else 1900 + suffix
        return str(inferred_year)

    if len(year_digits) == 2:
        suffix = int(year_digits)
        inferred_year = 2000 + suffix if suffix <= current_year % 100 else 1900 + suffix
        return str(inferred_year)

    return ""


def format_dob_from_parts(day_text, month_text, year_text, current_year=None):
    day_digits = _normalize_digit_text(day_text)
    month_digits = _normalize_digit_text(month_text)
    year_digits = _normalize_digit_text(year_text)

    if len(day_digits) < 2 or len(month_digits) < 2:
        return ""

    day_value = day_digits[:2]
    month_value = month_digits[:2]
    year_value = _normalize_year_digits(year_digits, current_year=current_year)

    if len(year_value) != 4:
        return ""

    try:
        date(int(year_value), int(month_value), int(day_value))
    except ValueError:
        return ""

    return f"{day_value}/{month_value}/{year_value}"


def normalize_address_line(text):
    clean = validate_and_clean(text, "address")
    if not clean:
        return ""

    tokens = clean.split()
    if not tokens:
        return ""

    if len(tokens) > 1 and len(tokens[-1]) == 1 and len("".join(tokens[:-1])) >= 4:
        tokens = tokens[:-1]

    compact_first = tokens[0].replace("/", "")
    if compact_first in ADDRESS_RELATION_PREFIXES:
        relation_prefix = compact_first[0]
        tokens[0] = f"{relation_prefix}/O"

    if len(tokens) == 2 and len(tokens[0]) == 1 and len(tokens[1]) >= 4:
        return "".join(tokens)

    short_token_count = sum(len(token) <= 1 for token in tokens)
    if len(tokens) >= 3 and short_token_count >= max(2, len(tokens) // 2):
        return "".join(tokens)

    return " ".join(tokens)


def validate_and_clean(text, field_type):
    """Removes OCR artifacts and formats dates/names."""
    clean = text.upper()

    # Remove printed labels that might get caught in the crop
    junk_words = (
        r"\b(SITC|SRCT|KAMERI|MRE|INSIVIAUAL|APPICACIE|WARNEE|SHOULD|FILL|"
        r"FATHER|NAME|ONLY|PLEASE|TICK|APPLICABTE|DAY|MONET|YEAR|MONTH)\b"
    )
    clean = re.sub(junk_words, "", clean)

    clean = _collapse_spaced_letters(clean)
    clean = re.sub(r"[^A-Z0-9\s\/]", " ", clean)

    if field_type in ["name", "father_name"]:
        clean = _normalize_alpha_noise(clean)
        clean = re.sub(r"[^A-Z\s]", "", clean)
        clean = " ".join([w for w in clean.split() if len(w) > 2])

    elif field_type == "dob":
        digits = _normalize_digit_text(clean)

        year_match = re.search(r"(19\d{2}|20\d{2})", digits)
        if year_match:
            year = year_match.group(1)
            idx = digits.find(year)
            if idx >= 4:
                day_month = digits[idx - 4 : idx]
                dob_value = format_dob_from_parts(day_month[:2], day_month[2:4], year)
                if dob_value:
                    return dob_value

        if len(digits) >= 7:
            dob_value = format_dob_from_parts(digits[:2], digits[2:4], digits[4:])
            if dob_value:
                return dob_value
        return ""

    elif field_type == "state":
        clean = _normalize_alpha_noise(clean)
        clean = re.sub(r"[^A-Z\-\s]", "", clean)
        clean = " ".join([w for w in clean.split() if len(w) > 2])
        clean = _fuzzy_match_choice(clean, INDIAN_STATES_AND_UTS)

    elif field_type == "pin":
        return _extract_pin_digits(clean)

    return re.sub(r"\s+", " ", clean).strip()


def parse_address(raw_address, extracted_pin=None, extracted_state=None, address_lines=None):
    """Splits a large address string into logical dictionary keys."""

    cleaned_lines = []
    for line in address_lines or []:
        clean_line = normalize_address_line(line)
        if clean_line:
            cleaned_lines.append(clean_line)

    if cleaned_lines:
        clean_address = " ".join(cleaned_lines)
    else:
        clean_address = validate_and_clean(raw_address, "address")

    clean_address = clean_address.replace("6", "G").replace("5", "S").replace("0", "O")

    junk = r"\b(PINZODE|ZCR|CODE|COURRIRY|NOME|INDIA|INOIA)\b"
    clean_address = re.sub(junk, "", clean_address)
    clean_address = re.sub(r"\s+", " ", clean_address).strip()

    addr_dict = {
        "full_address": clean_address,
        "area": "",
        "district": "",
        "city": "",
        "town_or_city": "",
        "line_items": cleaned_lines,
        "address_line_1": "",
        "village": "",
        "street_or_post_office": "",
        "area_or_locality": "",
        "state": extracted_state or "",
        "pin_code": extracted_pin or "",
        "country": "INDIA",
    }

    raw_pin = re.sub(r"[GO]", "0", clean_address).replace("S", "5")
    pin_match = re.search(r"\b\d{6}\b|\b\d{5}[L|I]\d{1}\b", raw_pin)
    if pin_match:
        clean_pin = re.sub(r"[L|I]", "1", pin_match.group(0))
        addr_dict["pin_code"] = clean_pin
        clean_address = re.sub(r"\b.{6}\b", "", clean_address, count=1).strip()

    meaningful_lines = [
        line
        for line in cleaned_lines
        if line not in {addr_dict["state"], "INDIA"}
    ]

    if meaningful_lines:
        if len(meaningful_lines) >= 1:
            addr_dict["address_line_1"] = meaningful_lines[0]
        if len(meaningful_lines) >= 2:
            addr_dict["village"] = meaningful_lines[1]
        if len(meaningful_lines) >= 3:
            addr_dict["street_or_post_office"] = meaningful_lines[2]
        if len(meaningful_lines) >= 4:
            addr_dict["area_or_locality"] = meaningful_lines[3]
        if len(meaningful_lines) >= 5:
            addr_dict["town_or_city"] = meaningful_lines[4]
            addr_dict["city"] = meaningful_lines[4]
            addr_dict["district"] = meaningful_lines[4]
            addr_dict["area"] = meaningful_lines[3]
            return addr_dict

        if len(meaningful_lines) >= 3:
            addr_dict["area"] = meaningful_lines[-3]
        elif len(meaningful_lines) >= 2:
            addr_dict["area"] = meaningful_lines[-2]
        else:
            addr_dict["area"] = meaningful_lines[-1]

        if len(meaningful_lines) >= 2:
            addr_dict["city"] = meaningful_lines[-2]
        else:
            addr_dict["city"] = meaningful_lines[-1]

        addr_dict["town_or_city"] = meaningful_lines[-1]
        addr_dict["district"] = meaningful_lines[-1]
    else:
        words = [w for w in clean_address.split() if len(w) > 2]
        if len(words) >= 1:
            addr_dict["state"] = words[-1]
        if len(words) >= 2:
            addr_dict["city"] = words[-2]
        if len(words) >= 3:
            addr_dict["area"] = words[-3]
        if len(words) >= 1:
            addr_dict["district"] = words[-1]

    return addr_dict
