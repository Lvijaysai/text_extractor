# backend/ocr_engine/preprocess.py
import cv2
import numpy as np

FORM_W = 1600
FORM_H = 2200


def resize_to_fixed(image):
    """Resize all input forms to a standard size."""
    return cv2.resize(image, (FORM_W, FORM_H), interpolation=cv2.INTER_CUBIC)


def to_clean_grayscale(image):
    """
    Convert color image to clean grayscale with better sharpness.
    This is the main filter for full-page preprocessing.
    """
    # 1. Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 2. Denoise while preserving edges
    gray = cv2.bilateralFilter(gray, 9, 25, 25)

    # 3. Improve local contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 4. Sharpen text and edges
    kernel = np.array(
        [
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0],
        ],
        dtype=np.float32,
    )
    sharp = cv2.filter2D(gray, -1, kernel)

    return cv2.cvtColor(sharp, cv2.COLOR_GRAY2BGR)


def enhance_contrast(image):
    """
    OCR-focused preprocessing for cropped text regions.
    Removes grid lines and improves handwritten text visibility.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 15
    )

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)

    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

    grid = cv2.add(h_lines, v_lines)
    grid = cv2.dilate(grid, np.ones((3, 3), np.uint8), iterations=1)

    text_only = cv2.subtract(binary, grid)
    clean_text = cv2.medianBlur(text_only, 3)

    heal_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    healed_text = cv2.morphologyEx(clean_text, cv2.MORPH_CLOSE, heal_kernel)

    final_img = cv2.bitwise_not(healed_text)
    return cv2.cvtColor(final_img, cv2.COLOR_GRAY2BGR)


def enhance_dob_darkness(image):
    """
    DOB-only preprocessing:
    pure white background and black digits.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        10,
    )

    kernel = np.ones((2, 2), np.uint8)
    thick = cv2.dilate(binary, kernel, iterations=1)

    final = cv2.bitwise_not(thick)
    return cv2.cvtColor(final, cv2.COLOR_GRAY2BGR)