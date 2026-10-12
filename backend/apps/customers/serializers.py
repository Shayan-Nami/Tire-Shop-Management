from rest_framework import serializers
from .models import Customer, Vehicle
from utils.persian import normalize_digits

class PersianNormalizedCharField(serializers.CharField):
    """
    فیلد متنی سفارشی جهت نرمال‌سازی ارقام فارسی به انگلیسی بدون تغییر مستقیم دیکشنری داده‌های اولیه.
    """
    def to_internal_value(self, data):
        if data is None:
            return None
        val = super().to_internal_value(data)
        if isinstance(val, str):
            norm = normalize_digits(val.strip())
            if not norm:
                return None if self.allow_null else ''
            return norm
        return val

class VehicleSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source='customer.full_name')
    license_plate = PersianNormalizedCharField(max_length=20)

    class Meta:
        model = Vehicle
        fields = ['vehicle_id', 'customer', 'customer_name', 'license_plate', 'model', 'year', 'tire_size_recommended', 'notes']

class CustomerSerializer(serializers.ModelSerializer):
    vehicles = VehicleSerializer(many=True, read_only=True)
    phone_number = PersianNormalizedCharField(
        max_length=20, required=False, allow_null=True, allow_blank=True,
        error_messages={'unique': 'این شماره تماس قبلاً برای مشتری دیگری ثبت شده است.'}
    )
    national_code = PersianNormalizedCharField(
        max_length=10, required=False, allow_null=True, allow_blank=True,
        error_messages={'unique': 'این کد ملی قبلاً برای مشتری دیگری ثبت شده است.'}
    )

    class Meta:
        model = Customer
        fields = ['customer_id', 'full_name', 'phone_number', 'national_code', 'address', 'created_at', 'updated_at', 'vehicles']
        read_only_fields = ['customer_id', 'created_at', 'updated_at']

    def validate_phone_number(self, value):
        if not value:
            return None
        norm = normalize_digits(str(value).strip())
        if not norm:
            return None
        qs = Customer.objects.filter(phone_number=norm)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("این شماره تماس قبلاً برای مشتری دیگری ثبت شده است.")
        return norm

    def validate_national_code(self, value):
        if not value:
            return None
        norm = normalize_digits(str(value).strip())
        if not norm:
            return None
        qs = Customer.objects.filter(national_code=norm)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("این کد ملی قبلاً برای مشتری دیگری ثبت شده است.")
        return norm
