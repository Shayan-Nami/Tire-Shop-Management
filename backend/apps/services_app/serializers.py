from decimal import Decimal

from rest_framework import serializers

from .models import Service


class ServiceSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        error_messages={'min_value': 'تعرفه خدمت نمی‌تواند منفی باشد.'},
    )

    class Meta:
        model = Service
        fields = ['service_id', 'service_name', 'price', 'description']
        extra_kwargs = {
            'service_name': {
                'error_messages': {
                    'unique': 'خدمتی با این نام قبلاً ثبت شده است.',
                }
            }
        }

    def validate_service_name(self, value: str) -> str:
        normalized = value.strip()
        qs = Service.objects.filter(service_name__iexact=normalized)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('خدمتی با این نام قبلاً ثبت شده است.')
        return normalized
