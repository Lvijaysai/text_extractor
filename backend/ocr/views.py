# backend/ocr/views.py
import os
import uuid
import cv2
import numpy as np
import logging
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from rest_framework.response import Response
from rest_framework.views import APIView

# Import the orchestrator from your newly built module
from ocr_engine.extractor import VisionOCRExtractor

logger = logging.getLogger(__name__)

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

            return Response({
                "status": "success",
                "profile": profile,
                "debug_crops": debug_urls,
                "image_url": f"{settings.MEDIA_URL}documents/{aligned_filename}"
            }, status=201)

        except Exception as e:
            logger.exception("Processing failed")
            return Response({"error": str(e)}, status=500)