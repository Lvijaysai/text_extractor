#backend/ocr/tests.py
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase

from ocr.views import OCRView
from ocr_engine.crop_refiner import refine_field_crop
from ocr_engine.extractor import VisionOCRExtractor, _resolve_gender_from_checkbox_scores
from ocr_engine.layout_detector import build_dynamic_rois_from_details
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


class DynamicLayoutDetectionTests(SimpleTestCase):
    @staticmethod
    def _box(x1, y1, x2, y2):
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    def test_dynamic_rois_are_built_from_anchor_rows(self):
        details = [
            {"text": "LAST NAME / SURNAME", "score": 0.95, "box": self._box(90, 628, 360, 660)},
            {"text": "GENDER", "score": 0.96, "box": self._box(70, 1038, 220, 1070)},
            {"text": "DATE OF BIRTH", "score": 0.96, "box": self._box(70, 1160, 340, 1192)},
            {"text": "LAST NAME / SURNAME", "score": 0.95, "box": self._box(90, 1374, 360, 1406)},
            {"text": "MOTHER'S NAME", "score": 0.96, "box": self._box(70, 1640, 320, 1672)},
            {"text": "RESIDENCE ADDRESS", "score": 0.96, "box": self._box(70, 1750, 360, 1782)},
            {
                "text": "STATE / UNION TERRITORY",
                "score": 0.96,
                "box": self._box(70, 2084, 420, 2116),
            },
        ]

        rois = build_dynamic_rois_from_details(details, (2200, 1600, 3))

        self.assertEqual(
            set(rois),
            {"name", "dob", "gender", "father_name", "address", "state", "pin"},
        )
        self.assertLess(rois["name"][1], rois["gender"][1])
        self.assertGreater(rois["dob"][1], 1172)
        self.assertGreater(rois["father_name"][1], rois["dob"][1])
        self.assertLessEqual(rois["address"][3], rois["state"][1])
        self.assertGreater(rois["pin"][0], rois["state"][0])

    def test_dynamic_rois_reject_noisy_bottom_labels(self):
        details = [
            {"text": "LAST NAME / SURNAME", "score": 0.95, "box": self._box(90, 520, 360, 552)},
            {"text": "GENDER", "score": 0.96, "box": self._box(70, 1030, 220, 1062)},
            {"text": "DATE OF BIRTH", "score": 0.96, "box": self._box(70, 1140, 340, 1172)},
            {"text": "RESIDENCE ADDRESS", "score": 0.96, "box": self._box(70, 1860, 360, 1892)},
            {
                "text": (
                    "RAND/STSET/LARA PART OTICE ARCALCCAIRYTEHTICNSOIRDTTON "
                    "TOVNCIYCTORRIC SRETEURON TERRTCRY KARNATAA"
                ),
                "score": 0.88,
                "box": self._box(70, 1960, 1420, 2050),
            },
        ]

        rois = build_dynamic_rois_from_details(details, (2200, 1600, 3))

        self.assertEqual(rois, {})


class CropRefinerTests(SimpleTestCase):
    def test_low_confidence_result_expands_crop(self):
        aligned = np.zeros((240, 240, 3), dtype=np.uint8)
        clean = np.zeros((240, 240, 3), dtype=np.uint8)
        base_roi = (80, 80, 160, 120)

        def extractor(base_crop, clean_crop):
            width = base_crop.shape[1]
            confidence = 0.55 if width <= 80 else 0.93
            return {
                "raw_text": "NARASEMHAPPA",
                "clean_text": "NARASEMHAPPA",
                "confidence": confidence,
                "debug_crop": base_crop,
                "address_lines": [],
            }

        best_roi, best_result = refine_field_crop(
            "name",
            base_roi,
            aligned,
            clean,
            extractor,
        )

        self.assertGreater(best_roi[2] - best_roi[0], base_roi[2] - base_roi[0])
        self.assertGreater(best_result["confidence"], 0.9)

    def test_label_leakage_result_shrinks_crop(self):
        aligned = np.zeros((240, 240, 3), dtype=np.uint8)
        clean = np.zeros((240, 240, 3), dtype=np.uint8)
        base_roi = (80, 80, 160, 120)

        def extractor(base_crop, clean_crop):
            width = base_crop.shape[1]
            if width >= 80:
                return {
                    "raw_text": "LAST NAME NARASEMHAPPA",
                    "clean_text": "NARASEMHAPPA",
                    "confidence": 0.92,
                    "debug_crop": base_crop,
                    "address_lines": [],
                }

            return {
                "raw_text": "NARASEMHAPPA",
                "clean_text": "NARASEMHAPPA",
                "confidence": 0.90,
                "debug_crop": base_crop,
                "address_lines": [],
            }

        best_roi, best_result = refine_field_crop(
            "name",
            base_roi,
            aligned,
            clean,
            extractor,
        )

        self.assertLess(best_roi[2] - best_roi[0], base_roi[2] - base_roi[0])
        self.assertEqual(best_result["raw_text"], "NARASEMHAPPA")


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

    @patch("ocr_engine.extractor.resize_to_fixed", side_effect=lambda image: image)
    @patch("ocr_engine.extractor.to_clean_grayscale", side_effect=lambda image: image)
    @patch(
        "ocr_engine.extractor.crop_roi",
        side_effect=AssertionError("fixed crop should not be used when dynamic ROIs exist"),
    )
    @patch(
        "ocr_engine.extractor.resolve_dynamic_rois",
        return_value={
            "name": (0, 0, 8, 8),
            "dob": (0, 0, 8, 8),
            "gender": (0, 0, 8, 8),
            "father_name": (0, 0, 8, 8),
            "address": (0, 0, 8, 8),
            "state": (0, 0, 8, 8),
            "pin": (0, 0, 8, 8),
        },
    )
    @patch("ocr_engine.extractor._extract_text_field")
    @patch("ocr_engine.extractor._extract_address_field")
    @patch("ocr_engine.extractor._extract_gender_field")
    @patch("ocr_engine.extractor._extract_dob_field")
    def test_dynamic_rois_take_precedence_over_fixed_coordinates(
        self,
        mock_extract_dob,
        mock_extract_gender,
        mock_extract_address,
        mock_extract_text,
        _mock_dynamic_rois,
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
            np.zeros((8, 8, 3), dtype=np.uint8),
        )
        mock_extract_gender.return_value = (
            "MALE FEMALE TRANSGENDER",
            "Male",
            0.77,
            np.zeros((8, 8, 3), dtype=np.uint8),
        )
        mock_extract_address.return_value = (
            "SO GANGAPPA QCNAGANAHALLI H CSUQ GAUDIBIDANUA CHIKKABALLAPUR",
            "SO GANGAPPA QCNAGANAHALLI H CSUQ GAUDIBIDANUA CHIKKABALLAPUR",
            0.88,
            ["S/O GANGAPPA", "QCNAGANAHALLI", "HCSUQ", "GAUDIBIDANUA", "CHIKKABALLAPUR"],
            np.zeros((8, 8, 3), dtype=np.uint8),
        )

        profile, crops_data, aligned_img = VisionOCRExtractor().process_image(
            np.zeros((10, 10, 3), dtype=np.uint8)
        )

        self.assertEqual(profile["dob"], "01/01/1957")
        self.assertEqual(profile["gender"], "Male")
        self.assertEqual(profile["location"]["state"], "KARNATAKA")
        self.assertEqual(crops_data["name"].shape, (8, 8, 3))
        self.assertEqual(aligned_img.shape, (10, 10, 3))

    @patch("ocr_engine.extractor.resize_to_fixed", side_effect=lambda image: image)
    @patch("ocr_engine.extractor.to_clean_grayscale", side_effect=lambda image: image)
    @patch(
        "ocr_engine.extractor.crop_roi",
        side_effect=lambda image, field: np.zeros((10, 10, 3), dtype=np.uint8),
    )
    @patch("ocr_engine.extractor._extract_text_field")
    @patch("ocr_engine.extractor._extract_dob_field")
    def test_process_image_can_filter_requested_output_fields(
        self,
        mock_extract_dob,
        mock_extract_text,
        _mock_crop_roi,
        _mock_to_clean_grayscale,
        _mock_resize_to_fixed,
    ):
        mock_extract_text.side_effect = lambda field, base_crop, clean_crop: {
            "name": ("NARASEMHAPPA", "NARASEMHAPPA", 0.93, base_crop),
        }[field]
        mock_extract_dob.return_value = (
            "01 01 145Y",
            "01/01/1957",
            0.88,
            np.zeros((10, 10, 3), dtype=np.uint8),
        )

        profile, crops_data, aligned_img = VisionOCRExtractor().process_image(
            np.zeros((10, 10, 3), dtype=np.uint8),
            output_fields=["full_name", "dob", "confidence_metrics"],
        )

        self.assertEqual(
            set(profile),
            {"full_name", "dob", "confidence_metrics"},
        )
        self.assertEqual(profile["full_name"], "NARASEMHAPPA")
        self.assertEqual(profile["dob"], "01/01/1957")
        self.assertEqual(set(profile["confidence_metrics"]), {"name", "dob"})
        self.assertEqual(set(crops_data), {"name", "dob"})
        self.assertEqual(aligned_img.shape, (10, 10, 3))


class OCRViewTests(SimpleTestCase):
    def test_parse_requested_fields_accepts_json_array(self):
        fields, error = OCRView()._parse_requested_fields(
            SimpleNamespace(data={"fields": '["full_name", "dob", "raw_extracted_text"]'})
        )

        self.assertIsNone(error)
        self.assertEqual(fields, ["full_name", "dob", "raw_extracted_text"])

    def test_parse_requested_fields_requires_primary_field(self):
        fields, error = OCRView()._parse_requested_fields(
            SimpleNamespace(data={"fields": '["confidence_metrics", "raw_extracted_text"]'})
        )

        self.assertIsNone(fields)
        self.assertEqual(error, "Select at least one extraction field.")
