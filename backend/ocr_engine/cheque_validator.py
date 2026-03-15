import cv2
import re
import logging
from rapidfuzz import fuzz
from .ocr_runner import reader
from ocr.models import BankAccount

# Initialize the logger for this module
logger = logging.getLogger(__name__)

class ChequeValidator:
    @staticmethod
    def parse_aadhaar_name(text):
        """Isolates the likely name string from Aadhaar OCR text."""
        noise = ["GOVERNMENT", "INDIA", "UNIQUE", "IDENTIFICATION", "AUTHORITY", "MALE", "FEMALE"]
        words = [w for w in text.split() if w not in noise and len(w) > 3]
        
        name = " ".join(words[:2]) if len(words) >= 2 else (words[0] if words else "")
        logger.info(f"[Aadhaar Parsing] Extracted Payee Name: '{name}'")
        return name

    @staticmethod
    def preprocess(img):
        """Production-grade cleanup: Grayscale -> Bilateral Filter -> Adaptive Threshold."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)
        return cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    @staticmethod
    def extract_text(img, doc_type="Document"):
        """Runs PaddleOCR on the cleaned image and returns a single uppercase string."""
        logger.debug(f"[{doc_type}] Starting image preprocessing and OCR...")
        processed = ChequeValidator.preprocess(img)
        raw = reader.ocr(processed, cls=False)
        
        text = " ".join([line[1][0].upper() for line in raw[0]]) if raw and raw[0] else ""
        
        # Log the exact string the OCR engine saw
        logger.info(f"\n--- {doc_type} OCR OUTPUT ---\n{text}\n---------------------------")
        return text

    @classmethod
    def validate(cls, cheque_img, pan_img, aadhaar_img):
        logger.info("=== STARTING CHEQUE VALIDATION PIPELINE ===")

        # 1. Extract Text from all documents
        chq_text = cls.extract_text(cheque_img, "CHEQUE")
        pan_text = cls.extract_text(pan_img, "PAN CARD")
        aad_text = cls.extract_text(aadhaar_img, "AADHAAR CARD")

        # 2. Extract specific name from Aadhaar (Person B)
        aad_name = cls.parse_aadhaar_name(aad_text)

        # 3. Find Account Number (Regex looks for 9 to 18 consecutive digits)
        acc_match = re.search(r'\b\d{9,18}\b', chq_text)
        acc_num = acc_match.group(0) if acc_match else ""
        logger.info(f"[Regex] Extracted Account Number from Cheque: '{acc_num}'")

        # 4. Check Database for Person A
        db_acc = BankAccount.objects.filter(account_number=acc_num).first()
        
        # 5. Apply Business Rules with detailed score logging
        acc_valid = db_acc is not None
        if acc_valid:
            logger.info(f"[Database] Account MATCH found. Account Holder: '{db_acc.account_holder_name}'")
        else:
            logger.warning(f"[Database] NO MATCH found for Account Number: '{acc_num}'")

        # Rule 2: Cheque Owner (Person A) matches PAN card
        pan_score = 0
        pan_valid = False
        if acc_valid:
            pan_score = fuzz.partial_ratio(db_acc.account_holder_name.upper(), pan_text)
            pan_valid = pan_score > 85
        logger.info(f"[Rule 2: PAN Match] Score: {pan_score}/100 | Passed: {pan_valid}")
        
        # Rule 3: Payee Name (Person B) matches Aadhaar
        payee_score = fuzz.partial_ratio(aad_name, chq_text) if aad_name else 0
        payee_valid = aad_name != "" and payee_score > 85
        logger.info(f"[Rule 3: Payee Match] Score: {payee_score}/100 | Passed: {payee_valid}")
        
        # Rule 4: Signature (Simplified for now)
        sig_valid = True 

        all_passed = all([acc_valid, pan_valid, payee_valid, sig_valid])
        
        final_decision = "Approved" if all_passed else "Rejected"
        logger.info(f"=== PIPELINE FINISHED. FINAL DECISION: {final_decision} ===")

        return {
            "account_valid": acc_valid,
            "pan_valid": pan_valid,
            "payee_valid": payee_valid,
            "signature_valid": sig_valid,
            "final_decision": final_decision
        }