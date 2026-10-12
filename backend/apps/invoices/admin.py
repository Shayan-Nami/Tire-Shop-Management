from decimal import Decimal
from django.contrib import admin
from django.db import models
from django.db.models import Sum, Subquery, OuterRef, Value, F
from django.db.models.functions import Coalesce, Greatest
from .models import (
    SalesInvoice, SalesInvoiceTireItem, SalesInvoiceServiceItem,
    PurchaseInvoice, PurchaseInvoiceTireItem, SalesReturn, SalesReturnItem,
    InvoiceSequence
)

class ReadOnlyDocumentAdminMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


class SalesInvoiceTireItemInline(ReadOnlyDocumentAdminMixin, admin.TabularInline):
    model = SalesInvoiceTireItem
    extra = 0

class SalesInvoiceServiceItemInline(ReadOnlyDocumentAdminMixin, admin.TabularInline):
    model = SalesInvoiceServiceItem
    extra = 0

@admin.register(SalesInvoice)
class SalesInvoiceAdmin(ReadOnlyDocumentAdminMixin, admin.ModelAdmin):
    list_display = (
        'sales_invoice_id', 'invoice_date', 'customer', 'vehicle',
        'status', 'payment_status', 'total_amount', 'returned_amount',
        'net_amount', 'created_by'
    )
    list_select_related = ('customer', 'vehicle', 'created_by')
    list_filter = ('status', 'payment_status', 'invoice_date')
    search_fields = ('customer__full_name', 'customer__phone_number', 'vehicle__license_plate')
    inlines = [SalesInvoiceTireItemInline, SalesInvoiceServiceItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        returned_subquery = SalesReturn.objects.filter(
            sales_invoice=OuterRef('pk')
        ).values('sales_invoice').annotate(
            total=Sum('total_refund_amount')
        ).values('total')

        return qs.annotate(
            returned_amount_annotated=Coalesce(
                Subquery(returned_subquery, output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2))
            )
        ).annotate(
            net_amount_annotated=Greatest(
                F('total_amount') - F('returned_amount_annotated'),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                output_field=models.DecimalField(max_digits=14, decimal_places=2)
            )
        )

class PurchaseInvoiceTireItemInline(ReadOnlyDocumentAdminMixin, admin.TabularInline):
    model = PurchaseInvoiceTireItem
    extra = 0

@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(ReadOnlyDocumentAdminMixin, admin.ModelAdmin):
    list_display = ('purchase_invoice_id', 'invoice_date', 'supplier', 'status', 'total_amount', 'created_by')
    list_select_related = ('supplier', 'created_by')
    list_filter = ('status', 'invoice_date', 'supplier')
    search_fields = ('supplier__supplier_name',)
    inlines = [PurchaseInvoiceTireItemInline]

class SalesReturnItemInline(admin.TabularInline):
    model = SalesReturnItem
    extra = 0
    readonly_fields = ('sales_invoice_tire_item', 'tire', 'quantity', 'unit_price', 'unit_cost', 'refund_amount')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(SalesReturn)
class SalesReturnAdmin(admin.ModelAdmin):
    list_display = ('sales_return_id', 'sales_invoice', 'return_date', 'total_refund_amount', 'created_by')
    list_filter = ('return_date',)
    search_fields = ('sales_invoice__customer__full_name', 'reason')
    readonly_fields = ('sales_return_id', 'sales_invoice', 'return_date', 'reason', 'total_refund_amount', 'created_by', 'created_at')
    inlines = [SalesReturnItemInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(InvoiceSequence)
class InvoiceSequenceAdmin(ReadOnlyDocumentAdminMixin, admin.ModelAdmin):
    list_display = ('doc_type', 'year', 'last_number')
    list_filter = ('doc_type', 'year')


