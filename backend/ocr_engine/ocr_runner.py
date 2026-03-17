# backend/ocr_engine/ocr_runner.py
import logging

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

def _sort_key(item):
    if item["box"] is None:
        return (0, 0)

    top = min(point[1] for point in item["box"])
    left = min(point[0] for point in item["box"])
    return (top, left)


def run_ocr_on_region_detailed(img, detect_text=True):
    """Runs PaddleOCR and returns joined text, confidence, and per-line metadata."""
    raw = reader.ocr(img, cls=False, det=detect_text)

    if not raw or not raw[0]:
        return "", 0.0, []

    results = []

    for line in raw[0]:
        if detect_text:
            box = line[0]
            text, score = line[1]
        else:
            box = None
            text, score = line
        results.append(
            {
                "text": text.upper().strip(),
                "score": float(score),
                "box": box,
            }
        )

    results.sort(key=_sort_key)

    texts = [item["text"] for item in results if item["text"]]
    confidences = [item["score"] for item in results]

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return " ".join(texts), round(avg_conf, 4), results


def run_ocr_on_region(img, detect_text=True):
    """Runs PaddleOCR and returns the joined text plus average confidence."""
    text, confidence, _ = run_ocr_on_region_detailed(img, detect_text=detect_text)
    return text, confidence
