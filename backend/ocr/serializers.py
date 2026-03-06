# backend/ocr/serializers.py
from rest_framework import serializers

from .models import ScannedDocument


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScannedDocument
        fields = ["image", "extracted_text"]  # Includes the image upload and the text field
        read_only_fields = ["extracted_text"]  # User uploads image, system generates text
