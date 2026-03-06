# backend/ocr/urls.py
from django.urls import path

from .views import OCRView

urlpatterns = [
    # This creates the endpoint: /scan/
    path("scan/", OCRView.as_view(), name="scan"),
]
