from decimal import Decimal
from rest_framework import serializers
from .models import Service

class ServiceSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        error_messages={'min_value': 'تعرفه خدمت نمی‌تواند منفی باشد.'}
    )

    class Meta:
        model = Service
        fields = ['service_id', 'service_name', 'price', 'description']
