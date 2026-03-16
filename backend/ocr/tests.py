#backend/ocr/tests.py
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase

from ocr_engine.extractor import VisionOCRExtractor
from ocr_engine.postprocess import validate_and_clean


class PostprocessTests(SimpleTestCase):
    def test_pin_parser_handles_box_separator_noise(self):
        self.assertEqual(validate_and_clean("ISL6LTL2ITLO", "pin"), "561210")

    def test_pin_parser_keeps_clean_pin_values(self):
        self.assertEqual(validate_and_clean("560001", "pin"), "560001")

    def test_pin_parser_ignores_label_noise(self):
        self.assertEqual(validate_and_clean("PIN CODE 560001", "pin"), "560001")


class VisionOCRExtractorTests(SimpleTestCase):
    @patch("ocr_engine.extractor.resize_to_fixed", side_effect=lambda image: image)
    @patch("ocr_engine.extractor.enhance_contrast", side_effect=lambda image: image)
    @patch("ocr_engine.extractor.crop_roi", side_effect=lambda image, field: field)
    @patch("ocr_engine.extractor.run_ocr_on_region")
    def test_profile_includes_raw_ocr_output(
        self,
        mock_run_ocr_on_region,
        _mock_crop_roi,
        _mock_enhance_contrast,
        _mock_resize_to_fixed,
    ):
        mock_run_ocr_on_region.side_effect = lambda crop, detect_text=True: {
            "name": ("NARASEMHAPPA", 0.93),
            "dob": ("DOY HOST YEAR 0 J 1 4 5 Y", 0.76),
            "gender": ("MALE", 0.77),
            "father_name": ("GANGAPPA", 0.90),
            "address": ("SO GAN GHPPA QCNAGANAHALLI HCSUQ GAUDIBIDANUA", 0.88),
            "state": ("KARNATAYA", 0.86),
            "pin": ("561210", 0.92),
        }[crop]

        profile, crops_data, aligned_img = VisionOCRExtractor().process_image(np.zeros((10, 10, 3)))

        self.assertEqual(profile["location"]["pincode"], "561210")
        self.assertEqual(profile["raw_extracted_text"]["pin"], "561210")
        self.assertEqual(profile["raw_extracted_text"]["dob"], "DOY HOST YEAR 0 J 1 4 5 Y")
        self.assertIn("pin", crops_data)
        self.assertEqual(aligned_img.shape, (10, 10, 3))
