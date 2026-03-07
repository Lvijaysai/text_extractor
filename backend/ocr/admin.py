
# backend/ocr/admin.py
from django.contrib import admin
from .models import BankAccount

# This tells Django to show this model in the admin dashboard
@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    # This makes the list view much easier to read
    list_display = ('account_number', 'account_holder_name')
    search_fields = ('account_number', 'account_holder_name')