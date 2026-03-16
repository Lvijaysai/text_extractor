# backend/ocr_engine/postprocess.py
import re


def _collapse_spaced_letters(text):
    """Merges box-separated letters back into whole words (G A N G -> GANG)"""
    clean = text
    while re.search(r"\b([A-Z0-9])\s+([A-Z0-9])\b", clean):
        clean = re.sub(r"\b([A-Z0-9])\s+([A-Z0-9])\b", r"\1\2", clean)
    return clean


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
        digits = _pin_token_to_digits(token, include_weak_ones=False)
        if len(digits) == 6:
            return digits
        if len(digits) > 6 and token.isdigit():
            return digits[:6]

    joined_numeric = "".join(char for char in text if char.isdigit())
    if len(joined_numeric) >= 6:
        return joined_numeric[:6]

    return ""


def validate_and_clean(text, field_type):
    """Removes OCR artifacts and formats dates/names."""
    clean = text.upper()

    # Remove printed labels that might get caught in the crop
    junk_words = r"\b(SITC|SRCT|KAMERI|MRE|INSIVIAUAL|APPICACIE|WARNEE|SHOULD|FILL|FATHER|NAME|ONLY|PLEASE|TICK|APPLICABTE|DAY|MONET|YEAR|MONTH)\b"
    clean = re.sub(junk_words, "", clean)

    clean = _collapse_spaced_letters(clean)
    clean = re.sub(r"[^A-Z0-9\s\/]", " ", clean)

    if field_type in ["name", "father_name"]:
        clean = re.sub(r"[^A-Z\s]", "", clean)
        clean = " ".join([w for w in clean.split() if len(w) > 2])

    elif field_type == "dob":
        # Only do safe number replacements (O to 0, S to 5, etc)
        clean = clean.replace("O", "0").replace("I", "1").replace("S", "5").replace("L", "1").replace("Z", "2").replace("B", "8").replace("Q", "9").replace("Y", "7")   
        digits = re.sub(r"[^0-9]", "", clean)

        # BULLETPROOF DATE ALGORITHM:
        # Searches the string for a valid year (19XX or 20XX), then counts exactly
        # 4 digits backwards to get the Day and Month, ignoring hallucinated '1's from grids.
        year_match = re.search(r"(19\d{2}|20\d{2})", digits)
        if year_match:
            year = year_match.group(1)
            idx = digits.find(year)
            if idx >= 4:
                day_month = digits[idx - 4 : idx]
                return f"{day_month[:2]}/{day_month[2:4]}/{year}"

        # Conservative fallback: only accept an exact 8-digit date string.
        if len(digits) == 8:
            d = digits
            return f"{d[:2]}/{d[2:4]}/{d[4:8]}"
        return ""

    elif field_type == "state":
        clean = re.sub(r"[^A-Z\-\s]", "", clean) # keep letters, hyphens, spaces
        clean = " ".join([w for w in clean.split() if len(w) > 2])

    elif field_type == "pin":
        return _extract_pin_digits(clean)
    
    return re.sub(r"\s+", " ", clean).strip()


def parse_address(raw_address, extracted_pin=None, extracted_state=None):
    """Splits a large address string into logical dictionary keys."""

    clean_address = validate_and_clean(raw_address, "address")

    # Fix common OCR hallucinated characters
    clean_address = clean_address.replace("6", "G").replace("5", "S").replace("0", "O")

    # Remove bottom-of-page printed junk
    junk = r"\b(PINZODE|ZCR|CODE|COURRIRY|NOME|INDIA|INOIA)\b"
    clean_address = re.sub(junk, "", clean_address)

    addr_dict = {
        "full_address": clean_address,
        "area": "",
        "city": "",
        "state": extracted_state or "",
        "pin_code": extracted_pin or "",
        "country": "INDIA",
    }

    # Find Pin Code
    raw_pin = re.sub(r"[GO]", "0", clean_address).replace("S", "5")
    pin_match = re.search(r"\b\d{6}\b|\b\d{5}[L|I]\d{1}\b", raw_pin)
    if pin_match:
        clean_pin = re.sub(r"[L|I]", "1", pin_match.group(0))
        addr_dict["pin_code"] = clean_pin
        clean_address = re.sub(r"\b.{6}\b", "", clean_address, count=1)

    words = [w for w in clean_address.split() if len(w) > 2]
    if len(words) >= 1:
        addr_dict["state"] = words[-1]
    if len(words) >= 2:
        addr_dict["city"] = words[-2]
    if len(words) >= 3:
        addr_dict["area"] = words[-3]

    return addr_dict
