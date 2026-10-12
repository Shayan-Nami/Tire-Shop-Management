from django.contrib import admin
from .models import Service

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('service_id', 'service_name', 'price')
    search_fields = ('service_name',)
    ordering = ('service_name',)
