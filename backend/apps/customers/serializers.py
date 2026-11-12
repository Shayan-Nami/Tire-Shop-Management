from __future__ import annotations

from rest_framework import serializers

from utils.persian import national_code_validator, normalize_optional_digits, phone_validator
from utils.serializers import PersianNormalizedCharField
from .models import Customer, Vehicle


def _validate_unique_customer_field(
    field_name: str,
    value: str | None,
    instance: Customer | None,
    error_message: str,
) -> str | None:
    norm = normalize_optional_digits(value)
    if not norm:
        return None
    qs = Customer.objects.filter(**{field_name: norm})
    if instance:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise serializers.ValidationError(error_message)
    return norm


class VehicleSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source='customer.full_name')
    license_plate = PersianNormalizedCharField(max_length=20)

    class Meta:
        model = Vehicle
        fields = ['vehicle_id', 'customer', 'customer_name', 'license_plate', 'model', 'year', 'tire_size_recommended', 'notes']


class CustomerSerializer(serializers.ModelSerializer):
    vehicles = VehicleSerializer(many=True, read_only=True)
    phone_number = PersianNormalizedCharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[phone_validator],
        error_messages={'unique': 'این شماره تماس قبلاً برای مشتری دیگری ثبت شده است.'},
    )
    national_code = PersianNormalizedCharField(
        max_length=10,
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[national_code_validator],
        error_messages={'unique': 'این کد ملی قبلاً برای مشتری دیگری ثبت شده است.'},
    )

    class Meta:
        model = Customer
        fields = ['customer_id', 'full_name', 'phone_number', 'national_code', 'address', 'created_at', 'updated_at', 'vehicles']
        read_only_fields = ['customer_id', 'created_at', 'updated_at']

    def validate_phone_number(self, value: str | None) -> str | None:
        return _validate_unique_customer_field(
            'phone_number',
            value,
            self.instance,
            'این شماره تماس قبلاً برای مشتری دیگری ثبت شده است.',
        )

    def validate_national_code(self, value: str | None) -> str | None:
        return _validate_unique_customer_field(
            'national_code',
            value,
            self.instance,
            'این کد ملی قبلاً برای مشتری دیگری ثبت شده است.',
        )
