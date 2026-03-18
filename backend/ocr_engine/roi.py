# backend/ocr_engine/roi.py
import json
import os
# LASER-CALIBRATED ZONAL COORDINATES
ROI_FILE_PATH = os.path.join(os.path.dirname(__file__), "rois.json")

DEFAULT_ROIS = {
    "name": [0.32, 0.275, 0.95, 0.320],
    "dob": [0.05, 0.545, 0.40, 0.578],
    "gender": [0.30, 0.470, 0.85, 0.510],
    "father_name": [0.32, 0.615, 0.95, 0.660],
    "address": [0.28, 0.810, 0.98, 0.940],
    "state": [0.07, 0.940, 0.40, 0.970],
    "pin": [0.41, 0.950, 0.57, 0.973],
}

def load_rois():
    """Loads ROIs from the JSON file, or creates it if it doesn't exist."""
    if os.path.exists(ROI_FILE_PATH):
        try:
            with open(ROI_FILE_PATH, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    
    # If file doesn't exist, create it with defaults
    save_rois(DEFAULT_ROIS)
    return DEFAULT_ROIS

def save_rois(new_rois):
    """Saves the new coordinates to the JSON file and updates memory."""
    with open(ROI_FILE_PATH, 'w') as f:
        json.dump(new_rois, f, indent=4)
    ROIS.update(new_rois)

# Global ROI dictionary loaded at startup
ROIS = load_rois()

def absolute_roi(image_shape, field):
    """Return an absolute ROI tuple from percentage coordinates."""
    x1_pct, y1_pct, x2_pct, y2_pct = ROIS.get(field, DEFAULT_ROIS[field])
    h, w = image_shape[:2]
    x1, y1 = int(x1_pct * w), int(y1_pct * h)
    x2, y2 = int(x2_pct * w), int(y2_pct * h)
    return (x1, y1, x2, y2)

def crop_absolute_roi(image, roi):
    """Crop an image from an absolute (x1, y1, x2, y2) ROI."""
    x1, y1, x2, y2 = roi
    return image[y1:y2, x1:x2]

def crop_roi(image, field):
    """Mathematically slices the image based on percentage constraints."""
    return crop_absolute_roi(image, absolute_roi(image.shape, field))