from django.contrib import admin
from .models import Brand, Size, Tire, StockMovement, StockProjectionRepair

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('brand_id', 'brand_name')
    search_fields = ('brand_name',)

@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ('size_id', 'size_name')
    search_fields = ('size_name',)

class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    can_delete = False
    readonly_fields = tuple(field.name for field in StockMovement._meta.fields)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Tire)
class TireAdmin(admin.ModelAdmin):
    list_display = ('tire_id', 'tire_name', 'brand', 'size', 'stock_quantity', 'sale_price', 'purchase_price', 'is_low_stock')
    list_select_related = ('brand', 'size')
    list_filter = ('brand', 'size')
    search_fields = ('tire_name', 'brand__brand_name', 'size__size_name')
    ordering = ('tire_name',)
    readonly_fields = ('stock_quantity',)
    inlines = [StockMovementInline]

    def get_readonly_fields(self, request, obj=None):
        return ('stock_quantity', 'purchase_price') if obj else ('stock_quantity',)

    def save_model(self, request, obj, form, change):
        if not change:
            return super().save_model(request, obj, form, change)
        writable_fields = {'tire_name', 'brand', 'size', 'sale_price', 'min_stock_alert'}
        update_fields = writable_fields.intersection(form.changed_data)
        if update_fields:
            obj.save(update_fields=update_fields)
        obj.refresh_from_db()

    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True
    is_low_stock.short_description = 'هشدار کسری؟'

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('movement_id', 'tire', 'quantity', 'movement_type', 'balance_after', 'user', 'created_at')
    list_select_related = ('tire', 'user')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('tire__tire_name', 'description')
    readonly_fields = tuple(field.name for field in StockMovement._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockProjectionRepair)
class StockProjectionRepairAdmin(admin.ModelAdmin):
    list_display = ('id', 'tire', 'stock_before', 'stock_after', 'user', 'created_at')
    list_select_related = ('tire', 'user')
    readonly_fields = tuple(field.name for field in StockProjectionRepair._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
