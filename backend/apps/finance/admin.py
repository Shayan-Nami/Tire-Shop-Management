from django.contrib import admin
from .models import ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher


@admin.register(ReceiptVoucher)
class ReceiptVoucherAdmin(admin.ModelAdmin):
    list_display = ('receipt_id', 'receipt_date', 'amount', 'sales_invoice', 'payment_method', 'is_cancelled')
    list_select_related = ('sales_invoice__customer', 'created_by')
    list_filter = ('is_cancelled', 'receipt_date', 'payment_method')
    search_fields = ('sales_invoice__customer__full_name', 'cancellation_reason')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]


@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'payment_date', 'amount', 'purchase_invoice', 'payment_method', 'is_cancelled')
    list_select_related = ('purchase_invoice__supplier', 'created_by')
    list_filter = ('is_cancelled', 'payment_date', 'payment_method')
    search_fields = ('purchase_invoice__supplier__supplier_name', 'cancellation_reason')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]


@admin.register(CustomerRefundVoucher)
class CustomerRefundVoucherAdmin(admin.ModelAdmin):
    list_display = ('refund_id', 'refund_date', 'amount', 'sales_invoice', 'sales_return', 'payment_method', 'is_cancelled')
    list_select_related = ('sales_invoice__customer', 'created_by')
    list_filter = ('is_cancelled', 'refund_date', 'payment_method')
    search_fields = ('sales_invoice__customer__full_name', 'cancellation_reason')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]
