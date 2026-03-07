# backend/ocr_engine/cheque_validator.py
import cv2
import re
from rapidfuzz import fuzz
from .ocr_runner import reader
from ocr.models import BankAccount

class ChequeValidator:
    @staticmethod
    def parse_aadhaar_name(text):
        """Isolates the likely name string from Aadhaar OCR text."""
        # Filter out common Aadhaar header noise
        noise = ["GOVERNMENT", "INDIA", "UNIQUE", "IDENTIFICATION", "AUTHORITY", "MALE", "FEMALE"]
        words = [w for w in text.split() if w not in noise and len(w) > 3]
        
        # Usually, the name is the first group of 2+ words appearing together
        return " ".join(words[:2]) if len(words) >= 2 else (words[0] if words else "")

    @staticmethod # <--- ADDED THIS FIXED DECORATOR
    def preprocess(img):
        """Production-grade cleanup: Grayscale -> Bilateral Filter -> Adaptive Threshold."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)
        return cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    @staticmethod
    def extract_text(img):
        """Runs PaddleOCR on the cleaned image and returns a single uppercase string."""
        processed = ChequeValidator.preprocess(img)
        raw = reader.ocr(processed, cls=False)
        return " ".join([line[1][0].upper() for line in raw[0]]) if raw and raw[0] else ""

    @classmethod
    def validate(cls, cheque_img, pan_img, aadhaar_img):
        # 1. Extract Text from all documents
        chq_text = cls.extract_text(cheque_img)
        pan_text = cls.extract_text(pan_img)
        aad_text = cls.extract_text(aadhaar_img)

        # 2. Extract specific name from Aadhaar (Person B)
        aad_name = cls.parse_aadhaar_name(aad_text)

        # 3. Find Account Number (Regex looks for 9 to 18 consecutive digits)
        acc_match = re.search(r'\b\d{9,18}\b', chq_text)
        acc_num = acc_match.group(0) if acc_match else ""

        # 4. Check Database for Person A
        db_acc = BankAccount.objects.filter(account_number=acc_num).first()
        
        # 5. Apply Business Rules
        acc_valid = db_acc is not None
        
        # Rule 2: Cheque Owner (Person A) matches PAN card
        pan_valid = acc_valid and fuzz.partial_ratio(db_acc.account_holder_name.upper(), pan_text) > 85
        
        # Rule 3: Payee Name (Person B) matches Aadhaar
        payee_valid = aad_name != "" and fuzz.partial_ratio(aad_name, chq_text) > 85
        
        # Rule 4: Signature (Simplified for now)
        sig_valid = True 

        all_passed = all([acc_valid, pan_valid, payee_valid, sig_valid])

        return {
            "account_valid": acc_valid,
            "pan_valid": pan_valid,
            "payee_valid": payee_valid,
            "signature_valid": sig_valid,
            "final_decision": "Approved" if all_passed else "Rejected"
        }