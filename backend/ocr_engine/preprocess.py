# backend/ocr_engine/preprocess.py
import cv2
import numpy as np

FORM_W = 1600
FORM_H = 2200

def resize_to_fixed(image):
    """Forces the document into a standard grid size."""
    return cv2.resize(image, (FORM_W, FORM_H), interpolation=cv2.INTER_CUBIC)

def enhance_contrast(image):
    """
    CLEAN GRID REMOVAL + NOISE FILTER
    Subtracts the grid flawlessly, filters out the dots/noise using Median Blur, 
    and heals the pen strokes without making the ink too thick.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 1. Binarize (Using a larger block size to ignore paper texture)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 15
    )
    
    # 2. Detect Grid Lines (Using long kernels so we don't grab letters)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
    
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
    
    # Combine horizontal and vertical lines
    grid = cv2.add(h_lines, v_lines)
    
    # 3. The "Cookie Cutter"
    # Dilate the grid slightly so it covers the glowing, fuzzy edges of the printed lines
    grid = cv2.dilate(grid, np.ones((3, 3), np.uint8), iterations=1)
    
    # 4. Erase the Grid
    # Subtracting leaves the text behind, but with clean cuts where lines used to be
    text_only = cv2.subtract(binary, grid)
    
    # 5. Destroy the Noise
    # Median Blur perfectly wipes out isolated dots while leaving text edges sharp
    clean_text = cv2.medianBlur(text_only, 3)
    
    # 6. Heal the Cuts (Without Thickening)
    # MORPH_CLOSE bridges the gaps without making the outside of the letter fatter
    heal_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    healed_text = cv2.morphologyEx(clean_text, cv2.MORPH_CLOSE, heal_kernel)
    
    # 7. Invert back to normal (black text, white background)
    final_img = cv2.bitwise_not(healed_text)
    
    return cv2.cvtColor(final_img, cv2.COLOR_GRAY2BGR)