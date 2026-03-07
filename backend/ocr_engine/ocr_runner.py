# backend/ocr_engine/ocr_runner.py
import logging

import cv2
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)

# INSTANTIATED GLOBALLY FOR PERFORMANCE (Singleton)
logger.info("Initializing PaddleOCR Engine...")
reader = PaddleOCR(use_gpu=False, use_angle_cls=True, lang="en", show_log=False)
logger.info("PaddleOCR Ready")


def run_ocr_on_region(image_crop):
    """Pads the crop and executes AI character extraction."""
    padded = cv2.copyMakeBorder(
        image_crop, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[255, 255, 255]
    )
    raw = reader.ocr(padded, cls=False)
    if not raw or not raw[0]:
        return ""

    texts = [line[1][0].upper().strip() for line in raw[0] if line[1][1] > 0.10]
    return " ".join(texts)
