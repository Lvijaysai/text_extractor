#backend/ocr_engine/extractor.py
from .preprocess import resize_to_fixed, enhance_contrast
from .roi import ROIS, crop_roi
from .ocr_runner import run_ocr_on_region
from .postprocess import validate_and_clean, parse_address
from .align import fix_perspective_and_skew

class VisionOCRExtractor:
    """The central orchestrator for the document extraction pipeline."""
    
    def process_image(self, original_img):
        # Step 2 & 3: Bypass warp for clean digital scans (uncomment if using camera photos)
        # flat_img = fix_perspective_and_skew(original_img)
        flat_img = original_img

        # Step 4: Standardization
        aligned_img = resize_to_fixed(flat_img)
        
        profile = {
            "name": "", "date_of_birth": "", "father_name": "", "gender": "Male",
            "address": {}
        }
        crops_data = {}

        for field in ROIS.keys():
            # Step 6: Crop
            crop_img = crop_roi(aligned_img, field)

            # Step 5: Denoise Grids
            if field in ["name", "father_name", "dob", "address"]:
                crop_img = enhance_contrast(crop_img)

            crops_data[field] = crop_img
            
            # Step 7: OCR
            raw_text = run_ocr_on_region(crop_img)

            # Step 8: Post-Processing Validate
            if field == "dob":
                profile["date_of_birth"] = validate_and_clean(raw_text, field)
            elif field == "name":
                profile["name"] = validate_and_clean(raw_text, "name")
            elif field == "father_name":
                profile["father_name"] = validate_and_clean(raw_text, "father_name")
            elif field == "address":
                clean_addr = validate_and_clean(raw_text, "address")
                profile["address"] = parse_address(clean_addr)
            elif field == "gender":
                if "FEMALE" in raw_text.upper(): profile["gender"] = "Female"
                elif "TRANSGENDER" in raw_text.upper(): profile["gender"] = "Transgender"

        return profile, crops_data, aligned_img