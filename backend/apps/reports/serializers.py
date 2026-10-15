from rest_framework import serializers

class DashboardStatsResponseSerializer(serializers.Serializer):
    today_revenue = serializers.FloatField(help_text='مبلغ فروش امروز به ریال/تومان')
    today_invoices_count = serializers.IntegerField(help_text='تعداد فاکتورهای امروز')
    total_receivables = serializers.FloatField(help_text='مجموع مطالبات و فاکتورهای نسیه')
    unpaid_invoices_count = serializers.IntegerField(help_text='تعداد فاکتورهای تسویه نشده')
    total_inventory_value = serializers.FloatField(help_text='ارزش ریالی کل انبار')
    total_tires_stock = serializers.IntegerField(help_text='تعداد کل لاستیک‌های موجود در انبار')
    low_stock_count = serializers.IntegerField(help_text='تعداد اقلام تایر زیر حد هشدار')

class SalesByBrandItemSerializer(serializers.Serializer):
    brand_name = serializers.CharField()
    total_quantity = serializers.IntegerField()
    total_revenue = serializers.FloatField()

class ProfitabilityItemSerializer(serializers.Serializer):
    tire_id = serializers.IntegerField()
    tire_name = serializers.CharField()
    brand_name = serializers.CharField()
    size_name = serializers.CharField()
    total_sold = serializers.IntegerField()
    total_revenue = serializers.FloatField()
    total_cost = serializers.FloatField()
    total_profit = serializers.FloatField()

class InventoryValueItemSerializer(serializers.Serializer):
    tire_id = serializers.IntegerField()
    tire_name = serializers.CharField()
    brand_name = serializers.CharField()
    size_name = serializers.CharField()
    stock_quantity = serializers.IntegerField()
    purchase_price = serializers.FloatField()
    inventory_value = serializers.FloatField()

class InventoryValueResponseSerializer(serializers.Serializer):
    total_inventory_value = serializers.FloatField()
    items = InventoryValueItemSerializer(many=True)

class SalesByDateRangeResponseSerializer(serializers.Serializer):
    total_invoices = serializers.IntegerField()
    total_sales_amount = serializers.FloatField(help_text='Net sales: gross sales less returns recorded in the period; may be negative.')
    gross_sales_amount = serializers.FloatField(help_text='Confirmed invoice totals in the period, after invoice discounts and before returns.')
    total_refund_amount = serializers.FloatField(help_text='Sales return amounts recorded in the period, independently of the original invoice date or cash refunds.')
    start_date = serializers.CharField(allow_null=True)
    end_date = serializers.CharField(allow_null=True)


class SalesByDateQuerySerializer(serializers.Serializer):
    start_date = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    end_date = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_start_date(self, value):
        if value:
            from utils.jalali import parse_jalali_or_gregorian_date
            parsed = parse_jalali_or_gregorian_date(value)
            if not parsed:
                raise serializers.ValidationError("فرمت تاریخ شروع نامعتبر است. لطفاً تاریخ شمسی (مانند ۱۴۰۳/۰۱/۰۱) یا میلادی (YYYY-MM-DD) وارد نمایید.")
        return value

    def validate_end_date(self, value):
        if value:
            from utils.jalali import parse_jalali_or_gregorian_date
            parsed = parse_jalali_or_gregorian_date(value)
            if not parsed:
                raise serializers.ValidationError("فرمت تاریخ پایان نامعتبر است. لطفاً تاریخ شمسی (مانند ۱۴۰۳/۰۱/۰۱) یا میلادی (YYYY-MM-DD) وارد نمایید.")
        return value


class SalesByBrandQuerySerializer(serializers.Serializer):
    brand_id = serializers.IntegerField(required=False, allow_null=True)

