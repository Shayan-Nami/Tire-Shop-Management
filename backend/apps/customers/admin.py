from django.contrib import admin
from .models import Customer, Vehicle

class VehicleInline(admin.TabularInline):
    model = Vehicle
    extra = 1

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_id', 'full_name', 'phone_number', 'national_code', 'created_at')
    search_fields = ('full_name', 'phone_number', 'national_code')
    list_filter = ('created_at',)
    inlines = [VehicleInline]

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('vehicle_id', 'license_plate', 'model', 'year', 'customer')
    search_fields = ('license_plate', 'model', 'customer__full_name', 'customer__phone_number')
    list_filter = ('model',)
