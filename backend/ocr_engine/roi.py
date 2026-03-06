# backend/ocr_engine/roi.py

# LASER-CALIBRATED ZONAL COORDINATES
ROIS = {
    "name": (0.32, 0.275, 0.95, 0.320),
    # DOB: Pushed down to bypass the "Day Month Year" label completely
    "dob": (0.05, 0.530, 0.40, 0.585),
    "gender": (0.30, 0.470, 0.85, 0.510),
    "father_name": (0.32, 0.615, 0.95, 0.660),
    # Address: Brought y2 UP to 0.940 so it cuts off the printed "Pincode" text at the bottom
    "address": (0.28, 0.810, 0.98, 0.940),
}


def crop_roi(image, field):
    """Mathematically slices the image based on percentage constraints."""
    x1_pct, y1_pct, x2_pct, y2_pct = ROIS[field]
    h, w = image.shape[:2]
    x1, y1 = int(x1_pct * w), int(y1_pct * h)
    x2, y2 = int(x2_pct * w), int(y2_pct * h)
    return image[y1:y2, x1:x2]
