# backend/ocr_engine/ocr_runner.py
import logging
import cv2
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)

# INSTANTIATED GLOBALLY FOR PERFORMANCE (Singleton)
logger.info("Initializing High-Precision PaddleOCR Engine...")
reader = PaddleOCR(
    use_gpu=False,
    enable_mkldnn=True, 
    use_angle_cls=True, 
    lang="en", 
    ocr_version="PP-OCRv4", 
    rec_algorithm="SVTR_LCNet", 
    det_db_thresh=0.3, 
    det_db_unclip_ratio=2.0,  # 🌟 ADDED: Expands boxes to catch cursive tails
    rec_batch_num=6, 
    show_log=False
)
logger.info("High-Precision Engine Ready")

def run_ocr_on_region(img):
    """Runs PaddleOCR and returns BOTH the text and the average confidence score."""
    raw = reader.ocr(img, cls=False)
    
    # If nothing is detected, return empty string and 0% confidence
    if not raw or not raw[0]:
        return "", 0.0

    texts = []
    confidences = []
    
    for line in raw[0]:
        # line[1][0] is the text, line[1][1] is the confidence float
        texts.append(line[1][0].upper())
        confidences.append(line[1][1])
        
    # Calculate the average confidence for the entire cropped region
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    
    return " ".join(texts), round(avg_conf, 4)