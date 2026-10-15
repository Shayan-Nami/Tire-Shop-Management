from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import (
    SalesInvoice, SalesInvoiceTireItem, SalesInvoiceServiceItem,
    PurchaseInvoice, PurchaseInvoiceTireItem, SalesReturn, SalesReturnItem,
    InvoiceStatus, PaymentStatus
)
from .services import (
    create_sales_invoice_service, create_purchase_invoice_service,
    create_sales_return_service
)
from apps.catalog.models import Tire
from apps.services_app.models import Service
from utils.jalali import format_jalali_date


class SalesInvoiceTireItemSerializer(serializers.ModelSerializer):
    tire_name = serializers.ReadOnlyField(source='tire.tire_name')
    brand_name = serializers.ReadOnlyField(source='tire.brand.brand_name')
    size_name = serializers.ReadOnlyField(source='tire.size.size_name')
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = SalesInvoiceTireItem
        fields = ['id', 'tire', 'tire_name', 'brand_name', 'size_name', 'quantity', 'unit_price', 'unit_cost', 'total_price']
        read_only_fields = ['id', 'unit_cost', 'total_price']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and hasattr(request.user, 'role') and request.user.role in ('TECHNICIAN', 'WAREHOUSE'):
            data.pop('unit_cost', None)
        return data

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=2))
    def get_total_price(self, obj):
        return obj.quantity * obj.unit_price

class SalesInvoiceServiceItemSerializer(serializers.ModelSerializer):
    service_name = serializers.ReadOnlyField(source='service.service_name')
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = SalesInvoiceServiceItem
        fields = ['id', 'service', 'service_name', 'quantity', 'unit_price', 'total_price']

    @extend_schema_field(serializers.DecimalField(max_digits=14, decimal_places=2))
    def get_total_price(self, obj):
        return obj.quantity * obj.unit_price

class SalesInvoiceSerializer(serializers.ModelSerializer):
    tire_items = SalesInvoiceTireItemSerializer(many=True, read_only=True)
    service_items = SalesInvoiceServiceItemSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source='customer.full_name')
    customer_phone = serializers.ReadOnlyField(source='customer.phone_number')
    vehicle_plate = serializers.ReadOnlyField(source='vehicle.license_plate')
    vehicle_model = serializers.ReadOnlyField(source='vehicle.model')
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    jalali_date = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    returned_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    net_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    excess_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SalesInvoice
        fields = [
            'sales_invoice_id', 'invoice_number', 'invoice_date', 'jalali_date', 'customer',
            'customer_name', 'customer_phone', 'vehicle', 'vehicle_plate',
            'vehicle_model', 'status', 'status_display', 'payment_status',
            'payment_status_display', 'discount_amount', 'discount_percent',
            'total_amount', 'returned_amount', 'net_amount', 'excess_amount',
            'paid_amount', 'remaining_amount', 'notes',
            'created_by', 'created_by_name', 'tire_items', 'service_items'
        ]
        read_only_fields = [
            'sales_invoice_id', 'invoice_number', 'total_amount', 'returned_amount',
            'net_amount', 'excess_amount', 'paid_amount', 'remaining_amount', 'created_by'
        ]


    @extend_schema_field(serializers.CharField)
    def get_jalali_date(self, obj):
        return format_jalali_date(obj.invoice_date)

class SalesInvoiceTireItemInputSerializer(serializers.Serializer):
    tire = serializers.PrimaryKeyRelatedField(
        queryset=Tire.objects.all(),
        error_messages={'does_not_exist': 'تایر با شناسه مشخص‌شده یافت نشد.'}
    )
    quantity = serializers.IntegerField(
        min_value=1,
        default=1,
        error_messages={'min_value': 'تعداد تایر باید حداقل ۱ باشد.'}
    )
    unit_price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        error_messages={'min_value': 'قیمت واحد تایر نمی‌تواند منفی باشد.'}
    )

class SalesInvoiceServiceItemInputSerializer(serializers.Serializer):
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        error_messages={'does_not_exist': 'خدمت با شناسه مشخص‌شده یافت نشد.'}
    )
    quantity = serializers.IntegerField(
        min_value=1,
        default=1,
        error_messages={'min_value': 'تعداد خدمت باید حداقل ۱ باشد.'}
    )
    unit_price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        error_messages={'min_value': 'تعرفه خدمت نمی‌تواند منفی باشد.'}
    )

class SalesInvoiceCreateSerializer(serializers.ModelSerializer):
    payment_method = serializers.CharField(max_length=50, required=False, default='کارتخوان / نقدی')
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    tire_items = SalesInvoiceTireItemInputSerializer(many=True, required=False)
    service_items = SalesInvoiceServiceItemInputSerializer(many=True, required=False)

    class Meta:
        model = SalesInvoice
        fields = [
            'sales_invoice_id', 'customer', 'vehicle', 'status', 'payment_status',
            'payment_method', 'reference_number',
            'discount_amount', 'discount_percent', 'total_amount', 'notes',
            'tire_items', 'service_items'
        ]
        read_only_fields = ['sales_invoice_id', 'total_amount']

    def validate(self, attrs):
        customer = attrs.get('customer')
        vehicle = attrs.get('vehicle')
        if vehicle and customer and vehicle.customer_id != customer.pk:
            raise serializers.ValidationError({"vehicle": "خودرو انتخاب‌شده متعلق به این مشتری نیست."})

        tire_items = attrs.get('tire_items') or []
        service_items = attrs.get('service_items') or []

        if not tire_items and not service_items:
            raise serializers.ValidationError("ثبت حداقل یک قلم تایر یا یک خدمت برای صدور فاکتور فروش الزامی است.")

        tire_ids = [item['tire'].pk for item in tire_items if 'tire' in item]
        if len(tire_ids) != len(set(tire_ids)):
            raise serializers.ValidationError({"tire_items": "تایر تکراری در اقلام فاکتور یافت شد. لطفاً تعداد را تجمیع نمایید."})

        service_ids = [item['service'].pk for item in service_items if 'service' in item]
        if len(service_ids) != len(set(service_ids)):
            raise serializers.ValidationError({"service_items": "خدمت تکراری در اقلام فاکتور یافت شد. لطفاً تعداد را تجمیع نمایید."})

        discount_amount = attrs.get('discount_amount', 0)
        discount_percent = attrs.get('discount_percent', 0)

        if discount_percent is not None:
            d_pct = Decimal(str(discount_percent))
            if d_pct < Decimal('0.00') or d_pct > Decimal('100.00'):
                raise serializers.ValidationError({"discount_percent": "درصد تخفیف باید عددی بین ۰ تا ۱۰۰ باشد."})

        if discount_amount is not None:
            d_amt = Decimal(str(discount_amount))
            if d_amt < Decimal('0.00'):
                raise serializers.ValidationError({"discount_amount": "مبلغ تخفیف نمی‌تواند منفی باشد."})

        if discount_amount and discount_percent and Decimal(str(discount_amount)) > 0 and Decimal(str(discount_percent)) > 0:
            raise serializers.ValidationError("امکان اعمال هم‌زمان تخفیف مبلغی و درصدی وجود ندارد.")

        # بررسی عدم تجاوز تخفیف مبلغی از جمع کل اقلام
        if discount_amount and Decimal(str(discount_amount)) > 0:
            subtotal = Decimal('0.00')
            for item in tire_items:
                qty = item.get('quantity', 1)
                unit_p_val = item.get('unit_price')
                unit_p = Decimal(str(unit_p_val)) if unit_p_val is not None else item['tire'].sale_price
                subtotal += qty * unit_p
            for item in service_items:
                qty = item.get('quantity', 1)
                unit_p_val = item.get('unit_price')
                unit_p = Decimal(str(unit_p_val)) if unit_p_val is not None else item['service'].price
                subtotal += qty * unit_p

            if Decimal(str(discount_amount)) > subtotal:
                raise serializers.ValidationError({
                    "discount_amount": f"مبلغ تخفیف ({Decimal(str(discount_amount)):,.0f}) نمی‌تواند از جمع کل اقلام فاکتور ({subtotal:,.0f}) بیشتر باشد."
                })

        status = attrs.get('status')
        if status == InvoiceStatus.CANCELLED:
            raise serializers.ValidationError({"status": "امکان صدور مستقیم فاکتور در وضعیت لغو شده وجود ندارد."})

        payment_status = attrs.get('payment_status')
        if payment_status == PaymentStatus.PARTIAL:
            raise serializers.ValidationError({"payment_status": "امکان ثبت مستقیم فاکتور در وضعیت نیمه‌پرداخت در بدو صدور وجود ندارد."})

        return attrs

    def create(self, validated_data):
        tire_items = validated_data.pop('tire_items', [])
        service_items = validated_data.pop('service_items', [])
        user = self.context['request'].user if 'request' in self.context else None

        prepared_tire_items = []
        for item in tire_items:
            tire_obj = item['tire']
            unit_p_val = item.get('unit_price')
            prepared_tire_items.append({
                'tire': tire_obj,
                'quantity': item['quantity'],
                'unit_price': unit_p_val if unit_p_val is not None else tire_obj.sale_price
            })

        prepared_service_items = []
        for item in service_items:
            service_obj = item['service']
            unit_p_val = item.get('unit_price')
            prepared_service_items.append({
                'service': service_obj,
                'quantity': item.get('quantity', 1),
                'unit_price': unit_p_val if unit_p_val is not None else service_obj.price
            })

        return create_sales_invoice_service(
            customer=validated_data.get('customer'),
            vehicle=validated_data.get('vehicle'),
            tire_items_data=prepared_tire_items,
            service_items_data=prepared_service_items,
            discount_amount=validated_data.get('discount_amount', 0),
            discount_percent=validated_data.get('discount_percent', 0),
            status=validated_data.get('status', InvoiceStatus.CONFIRMED),
            payment_status=validated_data.get('payment_status'),
            payment_method=validated_data.get('payment_method', 'کارتخوان / نقدی'),
            reference_number=validated_data.get('reference_number', ''),
            notes=validated_data.get('notes', ''),
            created_by=user
        )

class PurchaseInvoiceTireItemSerializer(serializers.ModelSerializer):
    tire_name = serializers.ReadOnlyField(source='tire.tire_name')

    class Meta:
        model = PurchaseInvoiceTireItem
        fields = ['id', 'tire', 'tire_name', 'quantity', 'unit_cost']

class PurchaseInvoiceSerializer(serializers.ModelSerializer):
    tire_items = PurchaseInvoiceTireItemSerializer(many=True, read_only=True)
    supplier_name = serializers.ReadOnlyField(source='supplier.supplier_name')
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    jalali_date = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)

    class Meta:
        model = PurchaseInvoice
        fields = [
            'purchase_invoice_id', 'invoice_number', 'invoice_date', 'jalali_date',
            'supplier', 'supplier_name', 'status', 'status_display',
            'payment_status', 'payment_status_display',
            'total_amount', 'created_by', 'created_by_name', 'tire_items'
        ]
        read_only_fields = ['purchase_invoice_id', 'invoice_number', 'payment_status', 'total_amount', 'created_by']

    @extend_schema_field(serializers.CharField)
    def get_jalali_date(self, obj):
        return format_jalali_date(obj.invoice_date)

class PurchaseInvoiceTireItemInputSerializer(serializers.Serializer):
    tire = serializers.PrimaryKeyRelatedField(
        queryset=Tire.objects.all(),
        error_messages={'does_not_exist': 'تایر با شناسه مشخص‌شده یافت نشد.'}
    )
    quantity = serializers.IntegerField(
        min_value=1,
        default=1,
        error_messages={'min_value': 'تعداد خرید باید حداقل ۱ باشد.'}
    )
    unit_cost = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        error_messages={'min_value': 'بهای خرید واحد نمی‌تواند منفی باشد.'}
    )

class PurchaseInvoiceCreateSerializer(serializers.ModelSerializer):
    tire_items = PurchaseInvoiceTireItemInputSerializer(many=True, required=True)

    class Meta:
        model = PurchaseInvoice
        fields = ['purchase_invoice_id', 'supplier', 'total_amount', 'tire_items']
        read_only_fields = ['purchase_invoice_id', 'total_amount']

    def validate_tire_items(self, value):
        if not value:
            raise serializers.ValidationError("ثبت حداقل یک قلم تایر برای فاکتور خرید الزامی است.")
        tire_ids = [item['tire'].pk for item in value if 'tire' in item]
        if len(tire_ids) != len(set(tire_ids)):
            raise serializers.ValidationError("تایر تکراری در اقلام فاکتور خرید یافت شد. لطفاً تعداد را در یک ردیف تجمیع نمایید.")
        return value

    def create(self, validated_data):
        tire_items = validated_data.pop('tire_items', [])
        user = self.context['request'].user if 'request' in self.context else None

        prepared_tire_items = []
        for item in tire_items:
            tire_obj = item['tire']
            unit_c_val = item.get('unit_cost')
            prepared_tire_items.append({
                'tire': tire_obj,
                'quantity': item['quantity'],
                'unit_cost': unit_c_val if unit_c_val is not None else tire_obj.purchase_price
            })

        return create_purchase_invoice_service(
            supplier=validated_data['supplier'],
            tire_items_data=prepared_tire_items,
            created_by=user
        )

class SalesReturnItemSerializer(serializers.ModelSerializer):
    tire_name = serializers.ReadOnlyField(source='tire.tire_name')
    brand_name = serializers.ReadOnlyField(source='tire.brand.brand_name')

    class Meta:
        model = SalesReturnItem
        fields = [
            'id', 'sales_invoice_tire_item', 'tire', 'tire_name', 'brand_name',
            'quantity', 'unit_price', 'unit_cost', 'refund_amount'
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and hasattr(request.user, 'role') and request.user.role == 'TECHNICIAN':
            data.pop('unit_cost', None)
        return data

class SalesReturnItemInputSerializer(serializers.Serializer):
    sales_invoice_tire_item_id = serializers.IntegerField(
        required=True,
        error_messages={'required': 'شناسه قلم فاکتور الزامی است.'}
    )
    quantity = serializers.IntegerField(
        min_value=1,
        default=1,
        error_messages={'min_value': 'تعداد مرجوعی باید حداقل ۱ باشد.'}
    )

class SalesReturnSerializer(serializers.ModelSerializer):
    items = SalesReturnItemSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source='sales_invoice.customer.full_name')
    customer_phone = serializers.ReadOnlyField(source='sales_invoice.customer.phone_number')
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    jalali_date = serializers.SerializerMethodField()

    class Meta:
        model = SalesReturn
        fields = [
            'sales_return_id', 'sales_invoice', 'customer_name', 'customer_phone',
            'return_date', 'jalali_date', 'reason', 'total_refund_amount',
            'created_by', 'created_by_name', 'items'
        ]
        read_only_fields = ['sales_return_id', 'total_refund_amount', 'created_by']

    @extend_schema_field(serializers.CharField)
    def get_jalali_date(self, obj):
        return format_jalali_date(obj.return_date)

class SalesReturnCreateSerializer(serializers.Serializer):
    sales_invoice = serializers.PrimaryKeyRelatedField(
        queryset=SalesInvoice.objects.all(),
        required=True,
        error_messages={'does_not_exist': 'فاکتور فروش با این شناسه یافت نشد.'}
    )
    return_date = serializers.DateTimeField(
        required=False,
        default=timezone.now
    )
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'ثبت دلیل / شرح مرجوعی الزامی است.',
            'blank': 'ثبت دلیل / شرح مرجوعی الزامی است.'
        }
    )
    items = SalesReturnItemInputSerializer(many=True, required=True)

    def validate_return_date(self, value):
        if value and value > timezone.now():
            raise serializers.ValidationError("تاریخ مرجوعی نمی‌تواند در آینده باشد.")
        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("ثبت حداقل یک قلم تایر جهت مرجوعی الزامی است.")
        return value

    def validate(self, attrs):
        invoice = attrs.get('sales_invoice')
        items = attrs.get('items', [])
        if not items:
            raise serializers.ValidationError({"items": "ثبت حداقل یک قلم تایر جهت مرجوعی الزامی است."})

        item_ids = [item.get('sales_invoice_tire_item_id') for item in items]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError({"items": "قلم تایر تکراری در اقلام مرجوعی یافت شد. لطفاً تعداد را تجمیع نمایید."})

        valid_item_ids = set(invoice.tire_items.values_list('id', flat=True))
        for item in items:
            t_id = item.get('sales_invoice_tire_item_id')
            if t_id not in valid_item_ids:
                raise serializers.ValidationError({
                    "items": f"قلم با شناسه {t_id} متعلق به فاکتور فروش #{invoice.sales_invoice_id} نیست."
                })
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user if 'request' in self.context else None
        return create_sales_return_service(
            invoice=validated_data['sales_invoice'],
            items_data=validated_data['items'],
            reason=validated_data['reason'],
            return_date=validated_data.get('return_date'),
            user=user,
            auto_refund=True
        )

