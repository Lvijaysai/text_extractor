# backend/ocr_engine/preprocess.py
import cv2
import numpy as np

FORM_W = 1200
FORM_H = 1700


def resize_to_fixed(image):
    """Forces the document into a standard grid size."""
    return cv2.resize(image, (FORM_W, FORM_H), interpolation=cv2.INTER_CUBIC)


def enhance_contrast(image):
    """
    GRID SUBTRACTION & STROKE REPAIR
    This algorithm isolates the grid, deletes it, and then uses Morphological Closing
    to automatically bridge the gaps where the grid chopped the handwriting.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 1. Binarize (Inverted: Text and Lines become White, Background becomes Black)
    # Using 150 as a cutoff to grab the pen ink and the dark printed lines
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

    # 2. Detect the Grid Lines
    # Horizontal lines
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

    # Vertical lines
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 20))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

    # Combine lines and dilate slightly to ensure we grab the full thickness of the box
    grid = cv2.add(h_lines, v_lines)
    grid = cv2.dilate(grid, np.ones((2, 2), np.uint8), iterations=1)

    # 3. Delete the Grid
    # Subtracting the grid from the binary image leaves ONLY the text.
    # However, the text will have cuts/gaps where the lines used to intersect.
    text_only = cv2.subtract(binary, grid)

    # 4. Repair the Broken Strokes (The Magic Step)
    # "Morphological Closing" dilates the text to bridge the gaps, then erodes the edges
    # so the letters don't become giant blobs. It sews the broken 'H' and 'O' back together!
    repair_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    repaired_text = cv2.morphologyEx(text_only, cv2.MORPH_CLOSE, repair_kernel)

    # Give the repaired text a tiny thickness boost so the AI can read it easily
    repaired_text = cv2.dilate(repaired_text, np.ones((2, 2), np.uint8), iterations=1)

    # 5. Invert back to Normal (Black text on White background)
    result = cv2.bitwise_not(repaired_text)

    # Convert back to 3-channel image for PaddleOCR
    return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
