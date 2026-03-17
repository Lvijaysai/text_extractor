#backend/ocr/tests.py
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase

from ocr_engine.extractor import VisionOCRExtractor, _resolve_gender_from_checkbox_scores
from ocr_engine.postprocess import (
    format_dob_from_parts,
    normalize_address_line,
    parse_address,
    validate_and_clean,
)


class PostprocessTests(SimpleTestCase):
    def test_pin_parser_handles_box_separator_noise(self):
        self.assertEqual(validate_and_clean("ISL6LTL2ITLO", "pin"), "561210")

    def test_pin_parser_handles_weak_one_substitutions(self):
        self.assertEqual(validate_and_clean("56L210", "pin"), "561210")

    def test_pin_parser_keeps_clean_pin_values(self):
        self.assertEqual(validate_and_clean("560001", "pin"), "560001")

    def test_pin_parser_ignores_label_noise(self):
        self.assertEqual(validate_and_clean("PIN CODE 560001", "pin"), "560001")

    def test_state_parser_fuzzy_matches_known_state(self):
        self.assertEqual(validate_and_clean("KARNATAYA", "state"), "KARNATAKA")

    def test_dob_formatter_recovers_from_partial_century_noise(self):
        self.assertEqual(format_dob_from_parts("01", "01", "145Y"), "01/01/1957")

    def test_dob_formatter_accepts_boxed_year_digits(self):
        self.assertEqual(format_dob_from_parts("01", "01", "1454"), "01/01/1954")

    def test_address_line_normalizer_repairs_relation_prefix(self):
        self.assertEqual(normalize_address_line("SO! GANGHPPA"), "S/O GANGHPPA")

    def test_parse_address_maps_pan_form_rows_conservatively(self):
        parsed = parse_address(
            "",
            extracted_pin="561210",
            extracted_state="KARNATAKA",
            address_lines=[
                "S/O GANGAPPA",
                "SCNAGANAHALLI",
                "HCSUR",
                "GAUDIBIDANUR",
                "CHIKBALLAPUR",
            ],
        )

        self.assertEqual(parsed["address_line_1"], "S/O GANGAPPA")
        self.assertEqual(parsed["area_or_locality"], "GAUDIBIDANUR")
        self.assertEqual(parsed["town_or_city"], "CHIKBALLAPUR")
        self.assertEqual(parsed["city"], "CHIKBALLAPUR")
        self.assertEqual(parsed["district"], "CHIKBALLAPUR")


class GenderResolverTests(SimpleTestCase):
    def test_transgender_requires_clear_checkbox_advantage(self):
        gender, confidence = _resolve_gender_from_checkbox_scores(
            {
                "Male": 0.28,
                "Female": 0.10,
                "Transgender": 0.30,
            }
        )

        self.assertEqual(gender, "Male")
        self.assertGreater(confidence, 0)

    def test_transgender_is_allowed_when_checkbox_is_clearly_stronger(self):
        gender, confidence = _resolve_gender_from_checkbox_scores(
            {
                "Male": 0.05,
                "Female": 0.04,
                "Transgender": 0.55,
            }
        )

        self.assertEqual(gender, "Transgender")
        self.assertGreater(confidence, 0.2)


class VisionOCRExtractorTests(SimpleTestCase):
    @patch("ocr_engine.extractor.resize_to_fixed", side_effect=lambda image: image)
    @patch("ocr_engine.extractor.to_clean_grayscale", side_effect=lambda image: image)
    @patch(
        "ocr_engine.extractor.crop_roi",
        side_effect=lambda image, field: np.zeros((10, 10, 3), dtype=np.uint8),
    )
    @patch("ocr_engine.extractor._extract_text_field")
    @patch("ocr_engine.extractor._extract_address_field")
    @patch("ocr_engine.extractor._extract_gender_field")
    @patch("ocr_engine.extractor._extract_dob_field")
    def test_profile_includes_raw_ocr_output(
        self,
        mock_extract_dob,
        mock_extract_gender,
        mock_extract_address,
        mock_extract_text,
        _mock_crop_roi,
        _mock_to_clean_grayscale,
        _mock_resize_to_fixed,
    ):
        mock_extract_text.side_effect = lambda field, base_crop, clean_crop: {
            "name": ("NARASEMHAPPA", "NARASEMHAPPA", 0.93, base_crop),
            "father_name": ("GANGAPPA", "GANGAPPA", 0.90, base_crop),
            "state": ("KARNATAYA", "KARNATAKA", 0.86, base_crop),
            "pin": ("561210", "561210", 0.92, base_crop),
        }[field]
        mock_extract_dob.return_value = (
            "01 01 145Y",
            "01/01/1957",
            0.88,
            np.zeros((10, 10, 3), dtype=np.uint8),
        )
        mock_extract_gender.return_value = (
            "MALE FEMALE TRANSGENDER",
            "Male",
            0.77,
            np.zeros((10, 10, 3), dtype=np.uint8),
        )
        mock_extract_address.return_value = (
            "SO GANGAPPA QCNAGANAHALLI H CSUQ GAUDIBIDANUA CHIKKABALLAPUR",
            "SO GANGAPPA QCNAGANAHALLI H CSUQ GAUDIBIDANUA CHIKKABALLAPUR",
            0.88,
            ["S/O GANGAPPA", "QCNAGANAHALLI", "HCSUQ", "GAUDIBIDANUA", "CHIKKABALLAPUR"],
            np.zeros((10, 10, 3), dtype=np.uint8),
        )

        profile, crops_data, aligned_img = VisionOCRExtractor().process_image(
            np.zeros((10, 10, 3), dtype=np.uint8)
        )

        self.assertEqual(profile["location"]["pincode"], "561210")
        self.assertEqual(profile["location"]["state"], "KARNATAKA")
        self.assertEqual(profile["dob"], "01/01/1957")
        self.assertEqual(profile["raw_extracted_text"]["pin"], "561210")
        self.assertEqual(profile["raw_extracted_text"]["dob"], "01 01 145Y")
        self.assertEqual(profile["address_details"]["city"], "CHIKKABALLAPUR")
        self.assertEqual(profile["address_details"]["district"], "CHIKKABALLAPUR")
        self.assertEqual(profile["address_details"]["town_or_city"], "CHIKKABALLAPUR")
        self.assertEqual(profile["address_details"]["address_line_1"], "S/O GANGAPPA")
        self.assertEqual(profile["address_details"]["lines"][1], "QCNAGANAHALLI")
        self.assertIn("pin", crops_data)
        self.assertEqual(aligned_img.shape, (10, 10, 3))
