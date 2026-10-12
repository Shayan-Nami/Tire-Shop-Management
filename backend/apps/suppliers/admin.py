from django.contrib import admin
from .models import Supplier

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('supplier_id', 'supplier_name', 'phone_number', 'address')
    search_fields = ('supplier_name', 'phone_number')
