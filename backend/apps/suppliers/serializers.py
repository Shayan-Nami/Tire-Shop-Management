from rest_framework import serializers

from utils.persian import supplier_phone_validator
from utils.serializers import PersianNormalizedCharField
from .models import Supplier


class SupplierSerializer(serializers.ModelSerializer):
    phone_number = PersianNormalizedCharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[supplier_phone_validator],
    )

    class Meta:
        model = Supplier
        fields = ['supplier_id', 'supplier_name', 'phone_number', 'address']
