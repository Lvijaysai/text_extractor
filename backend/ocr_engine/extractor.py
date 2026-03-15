# backend/ocr_engine/extractor.py
from .ocr_runner import run_ocr_on_region
from .postprocess import parse_address, validate_and_clean
from .preprocess import enhance_contrast, resize_to_fixed
from .roi import ROIS, crop_roi


class VisionOCRExtractor:
    """The central orchestrator for the document extraction pipeline."""

    def process_image(self, original_img):
        # Step 2 & 3: Bypass warp for clean digital scans (uncomment if using camera photos)
        # flat_img = fix_perspective_and_skew(original_img)
        flat_img = original_img

        # Step 4: Standardization
        aligned_img = resize_to_fixed(flat_img)

        profile = {
            "name": "",
            "date_of_birth": "",
            "father_name": "",
            "gender": "Male",
            "pin": "",
            "state": "",
            "address": {},
        }
        crops_data = {}
        raw_texts = {}
        for field in ROIS.keys():
            # Step 6: Crop
            crop_img = crop_roi(aligned_img, field)

            # Step 5: Denoise Grids
            if field in ["name", "father_name", "dob", "address", "state", "pin"]:
                crop_img = enhance_contrast(crop_img)

            crops_data[field] = crop_img

            # Step 7: OCR
            raw_text = run_ocr_on_region(crop_img)
            raw_texts[field] = raw_text

        state_val = validate_and_clean(raw_texts["state"], "state")
        pin_val = validate_and_clean(raw_texts["pin"], "pin")
        
        profile["state"] = state_val
        profile["pin"] = pin_val

        # Then, process all other fields
        profile["name"] = validate_and_clean(raw_texts["name"], "name")
        profile["date_of_birth"] = validate_and_clean(raw_texts["dob"], "dob")
        profile["father_name"] = validate_and_clean(raw_texts["father_name"], "father_name")
        
        gender_raw = raw_texts.get("gender", "").upper()
        if "FEMALE" in gender_raw:
            profile["gender"] = "Female"
        elif "TRANSGENDER" in raw_text.upper():
            profile["gender"] = "Transgender"

        clean_addr_string = validate_and_clean(raw_texts["address"], "address")
        profile["address"] = parse_address(clean_addr_string, pin_val, state_val)    

        return profile, crops_data, aligned_img
