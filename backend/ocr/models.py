# backend/ocr/models.py
from django.db import models


class BankAccount(models.Model):
    account_number = models.CharField(max_length=20, unique=True, db_index=True)
    account_holder_name = models.CharField(max_length=100) # Person A (Cheque Owner)
    
    # For a real system, you'd store an image path to compare signatures.
    # For now, we will store a reference path if you implement OpenCV SSIM later.
    signature_reference_path = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.account_number} - {self.account_holder_name}"