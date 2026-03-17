# backend/ocr_engine/roi.py

# LASER-CALIBRATED ZONAL COORDINATES
ROIS = {
    "name": (0.32, 0.275, 0.95, 0.320),
    # DOB: Tightened to focus on the handwritten boxes and cut most of the label row.
    "dob": (0.05, 0.545, 0.40, 0.578),
    "gender": (0.30, 0.470, 0.85, 0.510),
    "father_name": (0.32, 0.615, 0.95, 0.660),
    # Address: Brought y2 UP to 0.940 so it cuts off the printed "Pincode" text at the bottom
    "address": (0.28, 0.810, 0.98, 0.940),
    "state": (0.07, 0.940, 0.40, 0.970),
    # PIN: Shifted lower so OCR sees the digit row instead of the label/text above it.
    "pin": (0.41, 0.950, 0.57, 0.973),
}


def absolute_roi(image_shape, field):
    """Return an absolute ROI tuple from percentage coordinates."""
    x1_pct, y1_pct, x2_pct, y2_pct = ROIS[field]
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
