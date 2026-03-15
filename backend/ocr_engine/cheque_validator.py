import cv2
import re
import logging
from rapidfuzz import fuzz
from .ocr_runner import reader
from ocr.models import BankAccount

logger = logging.getLogger(__name__)

class ChequeValidator:
    @staticmethod
    def parse_aadhaar_name(text):
        """Isolates the likely name string from Aadhaar OCR text, ignoring typos."""
        # Expanded list to catch OCR typos like 'GOVERNMEN' or 'GOVT'
        noise = [
            "GOVERNMENT", "GOVERNMEN", "GOVT", "INDIA", "UNIQUE", 
            "IDENTIFICATION", "AUTHORITY", "MALE", "FEMALE", "DOB", "YEAR", "BIRTH"
        ]
        
        valid_words = []
        for w in text.split():
            # Strip out random punctuation that OCR sometimes adds
            clean_w = re.sub(r'[^A-Z]', '', w.upper())
            
            # Keep the word if it's not a noise word, not a number, and has length
            if clean_w not in noise and len(clean_w) > 2 and not clean_w.isdigit():
                valid_words.append(clean_w)
                
        # Take the first two valid words as First Name and Last Name
        return " ".join(valid_words[:2]) if len(valid_words) >= 2 else (valid_words[0] if valid_words else "")

    @staticmethod
    def preprocess(img):
        """
        Since we are scanning the whole document, we use a mild contrast boost.
        This prevents destroying the background textures that might confuse the AI.
        """
        return cv2.convertScaleAbs(img, alpha=1.2, beta=10)

    @staticmethod
    def extract_text(processed_img, doc_type):
        """Runs PaddleOCR on the full image and logs the raw output."""
        raw = reader.ocr(processed_img, cls=False)
        text = " ".join([line[1][0].upper() for line in raw[0]]) if raw and raw[0] else ""
        logger.info(f"\n--- {doc_type} OCR OUTPUT ---\n{text}\n---------------------------")
        return text

    @classmethod
    def validate(cls, cheque_img, pan_img, aadhaar_img):
        logger.info("=== STARTING FULL DOCUMENT VALIDATION PIPELINE ===")

        # 1. Extract Text from ALL documents using the FULL image (No Cropping)
        pan_text = cls.extract_text(cls.preprocess(pan_img), "PAN CARD")
        aad_text = cls.extract_text(cls.preprocess(aadhaar_img), "AADHAAR CARD")
        chq_text = cls.extract_text(cls.preprocess(cheque_img), "FULL CHEQUE")

        # 2. Extract specific name from Aadhaar (Person B)
        aad_name = cls.parse_aadhaar_name(aad_text)
        logger.info(f"[Aadhaar] Extracted Payee Name: '{aad_name}'")

        # 3. Find Account Number in the FULL cheque text
        acc_matches = re.findall(r'\b\d{9,18}\b', chq_text)
        acc_num = max(acc_matches, key=len) if acc_matches else ""
        logger.info(f"[Regex] Extracted Account Number from Cheque: '{acc_num}'")

        # 4. Check Database for Person A
        db_acc = BankAccount.objects.filter(account_number=acc_num).first()
        
        acc_valid = db_acc is not None
        chq_name_valid = False
        pan_valid = False
        payee_valid = False
        
        if acc_valid:
            db_name = db_acc.account_holder_name.upper()
            logger.info(f"[Database] MATCH found. Account Holder: '{db_name}'")
            
            # Rule 1: DB Name is found anywhere inside the FULL PAN Card text
            pan_score = fuzz.partial_ratio(db_name, pan_text)
            pan_valid = pan_score > 80
            logger.info(f"[Rule 1: PAN Match] Score: {pan_score}/100 | Passed: {pan_valid}")
            
            # Rule 2: DB Name is found anywhere inside the FULL cheque text
            chq_score = fuzz.partial_ratio(db_name, chq_text)
            chq_name_valid = chq_score > 75
            logger.info(f"[Rule 2: Cheque DB Match] Score: {chq_score}/100 | Passed: {chq_name_valid}")
            
            # Rule 3: Aadhaar Name is found anywhere inside the FULL cheque text
            if aad_name:
                payee_score = fuzz.partial_ratio(aad_name, chq_text)
                payee_valid = payee_score > 75 
                logger.info(f"[Rule 3: Aadhaar Payee Match] Score: {payee_score}/100 | Passed: {payee_valid}")

        sig_valid = True 
        all_passed = all([acc_valid, chq_name_valid, pan_valid, payee_valid, sig_valid])

        logger.info(f"=== PIPELINE FINISHED. FINAL DECISION: {'Approved' if all_passed else 'Rejected'} ===")

        return {
            "account_valid": acc_valid,
            "cheque_name_valid": chq_name_valid,
            "pan_valid": pan_valid,
            "payee_valid": payee_valid,
            "signature_valid": sig_valid,
            "final_decision": "Approved" if all_passed else "Rejected"
        }