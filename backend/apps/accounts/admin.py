from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'full_name', 'phone_number', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'full_name', 'phone_number')
    ordering = ('username',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('اطلاعات اختصاصی', {'fields': ('role', 'full_name', 'phone_number')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('اطلاعات اختصاصی', {'fields': ('role', 'full_name', 'phone_number')}),
    )
