#backend/ocr/models.py
from django.db import models

# Create your models here.
class ScannedDocument(models.Model):
    image = models.ImageField(upload_to='documents/')
    extracted_text = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Document {self.id} uploaded at {self.uploaded_at}"
    