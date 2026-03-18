# backend/ocr/views.py
import json
import logging
import os
import uuid

import cv2
import numpy as np
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from ocr_engine.cheque_validator import ChequeValidator
from ocr_engine.extractor import VisionOCRExtractor
from ocr_engine.output_fields import (
    ALLOWED_OUTPUT_FIELDS,
    DEFAULT_OUTPUT_FIELDS,
    has_selected_primary_fields,
)

logger = logging.getLogger(__name__)

class ChequeValidationView(APIView):
    def post(self, request, *args, **kwargs):
        files = {
            "cheque": request.FILES.get("cheque"),
            "pan": request.FILES.get("pan"),
            "aadhaar": request.FILES.get("aadhaar")
        }

        if not all(files.values()):
            return Response({"error": "Missing required documents."}, status=400)

        # Convert in-memory uploads directly to OpenCV image arrays (100% safe, no disk writing)
        cv2_images = {}
        for key, file_obj in files.items():
            img_bytes = file_obj.read()
            nparr = np.frombuffer(img_bytes, np.uint8)
            cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if cv_img is None:
                return Response({"error": f"Invalid image format for {key}."}, status=400)
            cv2_images[key] = cv_img

        # Run the validation pipeline
        results = ChequeValidator.validate(
            cv2_images["cheque"], 
            cv2_images["pan"], 
            cv2_images["aadhaar"]
        )

        # Explicitly structured JSON format
        return Response({
            "status": "success",
            "timestamp": timezone.now().isoformat(), # Example ISO timestamp
            "data": {
                "validation_details": {
                    "account_exists": results["account_valid"],
                    "pan_owner_match": results["pan_valid"],
                    "payee_aadhaar_match": results["payee_valid"],
                    "signature_verified": results["signature_valid"]
                },
                "final_decision": results["final_decision"],
                "engine_metadata": {
                    "ocr_engine": "PaddleOCR v4",
                    "matching_algorithm": "Levenshtein Fuzzy"
                }
            }
        }, status=200)
# Make sure to keep your existing OCRView below this!
# Initialize Extractor Globally
extractor = VisionOCRExtractor()


class OCRView(APIView):
    MAX_UPLOAD_BYTES = 10 * 1024 * 1024
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

    def _validate_upload(self, file_obj):
        if not file_obj:
            return "No image provided."
        if file_obj.size > self.MAX_UPLOAD_BYTES:
            return "Image too large. Max 10MB allowed."
        mime = (file_obj.content_type or "").lower()
        if mime and mime not in self.ALLOWED_MIME_TYPES:
            return "Unsupported image format."
        return None

    def _parse_requested_fields(self, request):
        raw_fields = request.data.get("fields")
        if raw_fields in (None, ""):
            return list(DEFAULT_OUTPUT_FIELDS), None

        parsed_fields = raw_fields
        if isinstance(raw_fields, str):
            raw_fields = raw_fields.strip()
            if not raw_fields:
                return list(DEFAULT_OUTPUT_FIELDS), None

            try:
                parsed_fields = json.loads(raw_fields)
            except json.JSONDecodeError:
                parsed_fields = [item.strip() for item in raw_fields.split(",") if item.strip()]

        if isinstance(parsed_fields, str):
            parsed_fields = [parsed_fields]

        if not isinstance(parsed_fields, (list, tuple, set)):
            return None, "Invalid fields payload."

        normalized_fields = []
        invalid_fields = []

        for field in parsed_fields:
            if not isinstance(field, str):
                invalid_fields.append(str(field))
                continue

            clean_field = field.strip()
            if not clean_field:
                continue

            if clean_field not in ALLOWED_OUTPUT_FIELDS:
                invalid_fields.append(clean_field)
                continue

            if clean_field not in normalized_fields:
                normalized_fields.append(clean_field)

        if invalid_fields:
            return None, f"Unsupported fields: {', '.join(invalid_fields)}"

        if not has_selected_primary_fields(normalized_fields):
            return None, "Select at least one extraction field."

        return normalized_fields, None

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("image")
        validation_error = self._validate_upload(file_obj)
        if validation_error:
            return Response({"error": validation_error}, status=400)

        requested_fields, fields_error = self._parse_requested_fields(request)
        if fields_error:
            return Response({"error": fields_error}, status=400)

        try:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "documents"))
            os.makedirs(fs.location, exist_ok=True)

            img_bytes = file_obj.read()
            nparr = np.frombuffer(img_bytes, np.uint8)
            original_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if original_img is None:
                return Response({"error": "Invalid image file."}, status=400)

            # --- DELEGATE TO THE OCR ENGINE ---
            profile, crops_data, aligned_img = extractor.process_image(
                original_img,
                output_fields=requested_fields,
            )
            # ----------------------------------

            unique_id = uuid.uuid4().hex[:8]
            debug_urls = {}

            for field, crop_img in crops_data.items():
                crop_filename = f"crop_{field}_{unique_id}.jpg"
                cv2.imwrite(fs.path(crop_filename), crop_img)
                debug_urls[field] = f"{settings.MEDIA_URL}documents/{crop_filename}"

            aligned_filename = f"aligned_{unique_id}.jpg"
            cv2.imwrite(fs.path(aligned_filename), aligned_img)

            return Response(
                {
                    "status": "success",
                    "data": profile,
                    "profile": profile,
                    "selected_fields": requested_fields,
                    "debug_crops": debug_urls,
                    "image_url": f"{settings.MEDIA_URL}documents/{aligned_filename}",
                },
                status=201,
            )

        except Exception as e:
            logger.exception("Processing failed")
            return Response({"error": str(e)}, status=500)
from ocr_engine.roi import ROIS, save_rois

class ROIConfigView(APIView):
    def get(self, request):
        """Fetch the current coordinates to display in the frontend."""
        return Response({"status": "success", "rois": ROIS}, status=200)

    def post(self, request):
        """Save new coordinates generated by the frontend drawing tool."""
        new_rois = request.data.get("rois")
        if not new_rois or not isinstance(new_rois, dict):
            return Response({"error": "Invalid payload."}, status=400)
        
        try:
            # Save the new coordinates to the JSON file
            save_rois(new_rois)
            return Response({"status": "success", "message": "Calibration saved!"}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)