# backend/ocr/urls.py
from django.urls import path

from .views import OCRView, ChequeValidationView, ROIConfigView

urlpatterns = [
    # This creates the endpoint: /scan/
    path("scan/", OCRView.as_view(), name="scan"),
    path("validate-cheque/", ChequeValidationView.as_view(), name="validate-cheque"),
    path("config/rois/", ROIConfigView.as_view(), name="config-rois"),
]
