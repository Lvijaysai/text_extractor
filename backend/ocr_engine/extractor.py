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
        confidences = {}
        for field in ROIS.keys():
            # Step 6: Crop
            crop_img = crop_roi(aligned_img, field)

            # Step 5: Denoise Grids
            if field in ["name", "father_name", "dob", "address", "state", "pin"]:
                crop_img = enhance_contrast(crop_img)

            crops_data[field] = crop_img

            # Step 7: OCR
            raw_text, confidence_score = run_ocr_on_region(crop_img)
            raw_texts[field] = raw_text
            confidences[field] = confidence_score

        state_val = validate_and_clean(raw_texts.get("state", ""), "state")
        pin_val = validate_and_clean(raw_texts.get("pin", ""), "pin")
        
        profile["state"] = state_val
        profile["pin"] = pin_val

        # Process all other fields
        profile["name"] = validate_and_clean(raw_texts.get("name", ""), "name")
        profile["date_of_birth"] = validate_and_clean(raw_texts.get("dob", ""), "dob")
        profile["father_name"] = validate_and_clean(raw_texts.get("father_name", ""), "father_name")
        
        gender_raw = raw_texts.get("gender", "").upper()
        if "FEMALE" in gender_raw:
            profile["gender"] = "Female"
        elif "TRANSGENDER" in gender_raw:
            profile["gender"] = "Transgender"

        clean_addr_string = validate_and_clean(raw_texts.get("address", ""), "address")
        profile["address"] = parse_address(clean_addr_string, pin_val, state_val)    

        # --- NEW: CONFIDENCE ROUTING LOGIC ---
        CONFIDENCE_THRESHOLD = 0.90
        requires_manual_review = False
        review_flags = {}

        for field, score in confidences.items():
            needs_review = score < CONFIDENCE_THRESHOLD
            if needs_review:
                requires_manual_review = True
                
            review_flags[field] = {
                "score_percentage": round(score * 100, 2),
                "needs_review": needs_review
            }

        formatted_profile = {
            "full_name": profile["name"],
            "dob": profile["date_of_birth"],
            "gender": profile["gender"],
            "father_name": profile["father_name"],
            "location": {
                "state": profile["state"],
                "pincode": profile["pin"],
                "country": "INDIA"
            },
            "address_details": {
                "raw_text": profile["address"]["full_address"],
                "city": profile["address"]["city"],
                "district": profile["address"]["area"]
            },
            "confidence_metrics": review_flags
        }    
    
        return formatted_profile, crops_data, aligned_img