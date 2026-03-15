# backend/ocr/views.py
import logging
import os
import uuid
from django.utils import timezone
import cv2
import numpy as np
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from rest_framework.response import Response
from rest_framework.views import APIView
from ocr_engine.cheque_validator import ChequeValidator
# Import the orchestrator from your newly built module
from ocr_engine.extractor import VisionOCRExtractor

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

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get("image")
        validation_error = self._validate_upload(file_obj)
        if validation_error:
            return Response({"error": validation_error}, status=400)

        try:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "documents"))
            os.makedirs(fs.location, exist_ok=True)

            img_bytes = file_obj.read()
            nparr = np.frombuffer(img_bytes, np.uint8)
            original_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if original_img is None:
                return Response({"error": "Invalid image file."}, status=400)

            # --- DELEGATE TO THE OCR ENGINE ---
            profile, crops_data, aligned_img = extractor.process_image(original_img)
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
                    "profile": profile,
                    "debug_crops": debug_urls,
                    "image_url": f"{settings.MEDIA_URL}documents/{aligned_filename}",
                },
                status=201,
            )

        except Exception as e:
            logger.exception("Processing failed")
            return Response({"error": str(e)}, status=500)
