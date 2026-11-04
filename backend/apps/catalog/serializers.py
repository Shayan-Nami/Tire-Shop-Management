from __future__ import annotations
from typing import Any
from decimal import Decimal
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Brand, Size, Tire, StockMovement
from utils.jalali import format_jalali_date

class BrandSerializer(serializers.ModelSerializer):
    tires_count = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ['brand_id', 'brand_name', 'tires_count']

    @extend_schema_field(serializers.IntegerField)
    def get_tires_count(self, obj: Brand) -> int:
        count = getattr(obj, 'tires_count', None)
        if count is not None:
            return count
        return obj.tires.count()

class SizeSerializer(serializers.ModelSerializer):
    tires_count = serializers.SerializerMethodField()

    class Meta:
        model = Size
        fields = ['size_id', 'size_name', 'tires_count']

    @extend_schema_field(serializers.IntegerField)
    def get_tires_count(self, obj: Size) -> int:
        count = getattr(obj, 'tires_count', None)
        if count is not None:
            return count
        return obj.tires.count()

class TireSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source='brand.brand_name')
    size_name = serializers.ReadOnlyField(source='size.size_name')
    is_low_stock = serializers.SerializerMethodField()
    sale_price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        error_messages={'min_value': 'قیمت فروش تایر نمی‌تواند منفی باشد.'}
    )
    purchase_price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        error_messages={'min_value': 'قیمت خرید تایر نمی‌تواند منفی باشد.'}
    )

    class Meta:
        model = Tire
        fields = [
            'tire_id', 'tire_name', 'brand', 'brand_name', 'size',
            'size_name', 'stock_quantity', 'sale_price', 'purchase_price',
            'min_stock_alert', 'is_low_stock'
        ]
        read_only_fields = ['stock_quantity']

    def update(self, instance: Tire, validated_data: dict[str, Any]) -> Tire:
        # Purchase cost is initialized on creation, then owned by purchase services.
        writable_fields = {'tire_name', 'brand', 'size', 'sale_price', 'min_stock_alert'}
        update_fields = writable_fields.intersection(validated_data)
        for field in update_fields:
            setattr(instance, field, validated_data[field])
        if update_fields:
            instance.save(update_fields=update_fields)
        instance.refresh_from_db()
        return instance

    @extend_schema_field(serializers.BooleanField)
    def get_is_low_stock(self, obj: Tire) -> bool:
        return obj.is_low_stock

    def to_representation(self, instance: Tire) -> dict[str, Any]:
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and hasattr(request.user, 'role') and request.user.role == 'TECHNICIAN':
            data.pop('purchase_price', None)
        return data

class StockAdjustmentSerializer(serializers.Serializer):
    counted_quantity = serializers.IntegerField(
        min_value=0,
        error_messages={'min_value': 'موجودی شمارش‌شده نمی‌تواند منفی باشد.'}
    )
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'ثبت دلیل / شرح انبارگردانی الزامی است.',
            'blank': 'ثبت دلیل / شرح انبارگردانی الزامی است.'
        }
    )

class StockMovementSerializer(serializers.ModelSerializer):
    tire_name = serializers.ReadOnlyField(source='tire.tire_name')
    brand_name = serializers.ReadOnlyField(source='tire.brand.brand_name')
    user_name = serializers.ReadOnlyField(source='user.full_name')
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    jalali_date = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            'movement_id', 'tire', 'tire_name', 'brand_name', 'quantity', 'movement_type',
            'movement_type_display', 'balance_after', 'sales_invoice',
            'purchase_invoice', 'unit_cost', 'user', 'user_name',
            'description', 'created_at', 'jalali_date'
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField)
    def get_jalali_date(self, obj: StockMovement) -> str:
        return format_jalali_date(obj.created_at)

    def to_representation(self, instance: StockMovement) -> dict[str, Any]:
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and hasattr(request.user, 'role'):
            if request.user.role in ('TECHNICIAN', 'WAREHOUSE'):
                data.pop('unit_cost', None)
            if request.user.role == 'TECHNICIAN':
                data.pop('purchase_invoice', None)
        return data
