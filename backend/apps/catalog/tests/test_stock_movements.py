import pytest
from decimal import Decimal
from django.urls import reverse
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer
from apps.suppliers.models import Supplier
from apps.invoices.models import InvoiceStatus
from apps.invoices.services import (
    create_sales_invoice_service,
    cancel_sales_invoice_service,
    create_purchase_invoice_service,
)

@pytest.fixture
def test_setup(db, manager_user):
    brand = Brand.objects.create(brand_name='بارز')
    size = Size.objects.create(size_name='205/55R16')
    tire = Tire.objects.create(
        tire_name='بارز پریمیوم 16',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('2000000.00'),
        sale_price=Decimal('2700000.00'),
        min_stock_alert=5
    )
    # ایجاد سند گردش اولیه موجودی برای همگام‌سازی کامل
    StockMovement.objects.create(
        tire=tire,
        quantity=20,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=20,
        unit_cost=Decimal('2000000.00'),
        user=manager_user,
        description='موجودی اولیه'
    )
    customer = Customer.objects.create(
        full_name='محمد حسینی',
        phone_number='09121112233'
    )
    supplier = Supplier.objects.create(
        supplier_name='شرکت پخش لاستیک مرکزی',
        phone_number='02188889999'
    )
    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'customer': customer,
        'supplier': supplier
    }

@pytest.mark.django_db
class TestStockMovementsAndLedger:

    def test_sales_invoice_creates_stock_movement_and_reduces_stock(self, test_setup, manager_user):
        """صدور فاکتور فروش، موجودی را کسر کرده و گردش خروج SALE ثبت می‌کند"""
        tire = test_setup['tire']
        customer = test_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[
                {'tire': tire, 'quantity': 4, 'unit_price': tire.sale_price}
            ],
            service_items_data=[],
            created_by=manager_user
        )

        tire.refresh_from_db()
        assert tire.stock_quantity == 16

        movement = StockMovement.objects.filter(
            tire=tire,
            movement_type=StockMovementType.SALE,
            sales_invoice=invoice
        ).first()
        assert movement is not None
        assert movement.quantity == -4
        assert movement.balance_after == 16
        assert movement.unit_cost == Decimal('2000000.00')
        assert movement.user == manager_user

    def test_cancel_sales_invoice_restores_stock_and_creates_cancellation_movement(
        self, test_setup, manager_user
    ):
        """لغو فاکتور فروش تایید شده، موجودی را بازگردانده و گردش SALE_CANCEL ثبت می‌کند"""
        tire = test_setup['tire']
        customer = test_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[
                {'tire': tire, 'quantity': 4, 'unit_price': tire.sale_price}
            ],
            service_items_data=[],
            created_by=manager_user
        )
        assert invoice.status == InvoiceStatus.CONFIRMED

        cancel_sales_invoice_service(invoice, user=manager_user)

        tire.refresh_from_db()
        assert tire.stock_quantity == 20

        cancel_movement = StockMovement.objects.filter(
            tire=tire,
            movement_type=StockMovementType.SALE_CANCEL,
            sales_invoice=invoice
        ).first()
        assert cancel_movement is not None
        assert cancel_movement.quantity == 4
        assert cancel_movement.balance_after == 20
        assert cancel_movement.user == manager_user

    def test_sales_invoice_fails_when_insufficient_stock(self, test_setup, manager_user):
        """در صورت عدم تکافوی موجودی، فاکتور صادر نشده و خطای اعتبارسنجی رخ می‌دهد"""
        tire = test_setup['tire']
        customer = test_setup['customer']

        with pytest.raises(ValidationError) as exc_info:
            create_sales_invoice_service(
                customer=customer,
                vehicle=None,
                tire_items_data=[
                    {'tire': tire, 'quantity': 25, 'unit_price': tire.sale_price}
                ],
                service_items_data=[],
                created_by=manager_user
            )
        assert "کافی نیست" in str(exc_info.value)
        tire.refresh_from_db()
        assert tire.stock_quantity == 20

    def test_purchase_invoice_creates_stock_movement_and_updates_purchase_price(
        self, test_setup, manager_user
    ):
        """فاکتور خرید موجودی را افزایش داده، گردش ورود ثبت می‌کند و نرخ خرید تایر را به‌روز می‌کند"""
        tire = test_setup['tire']
        supplier = test_setup['supplier']

        new_unit_cost = Decimal('2400000.00')
        invoice = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[
                {'tire': tire, 'quantity': 10, 'unit_cost': new_unit_cost}
            ],
            created_by=manager_user
        )

        tire.refresh_from_db()
        assert tire.stock_quantity == 30
        assert tire.purchase_price == new_unit_cost

        movement = StockMovement.objects.filter(
            tire=tire,
            movement_type=StockMovementType.PURCHASE,
            purchase_invoice=invoice
        ).first()
        assert movement is not None
        assert movement.quantity == 10
        assert movement.balance_after == 30
        assert movement.unit_cost == new_unit_cost
        assert movement.user == manager_user

    def test_tire_stock_quantity_cannot_be_modified_directly_via_api(
        self, test_setup, auth_client_manager
    ):
        """تغییر مستقیم فیلد stock_quantity از طریق API کاتالوگ مسدود است و نادیده گرفته می‌شود"""
        tire = test_setup['tire']
        url = reverse('tire-detail', args=[tire.pk])

        response = auth_client_manager.patch(url, {'stock_quantity': 999})
        assert response.status_code == 200

        tire.refresh_from_db()
        assert tire.stock_quantity == 20
        assert not StockMovement.objects.filter(balance_after=999).exists()

    def test_manual_stock_adjustment_permissions(
        self, test_setup, api_client, auth_client_technician, auth_client_warehouse, auth_client_manager
    ):
        """بررسی سطح دسترسی به اکشن انبارگردانی (adjust-stock)"""
        tire = test_setup['tire']
        url = reverse('tire-adjust-stock', args=[tire.pk])
        payload = {'counted_quantity': 25, 'reason': 'انبارگردانی'}

        # کاربر احرازهویت‌نشده
        res_anon = api_client.post(url, payload)
        assert res_anon.status_code == 401

        # تکنسین دسترسی ندارد (403)
        res_tech = auth_client_technician.post(url, payload)
        assert res_tech.status_code == 403

        # انباردار مجاز است (200)
        res_wh = auth_client_warehouse.post(url, payload)
        assert res_wh.status_code == 200

        # مدیر مجاز است (200)
        res_mgr = auth_client_manager.post(url, {'counted_quantity': 30, 'reason': 'اصلاح مدیر'})
        assert res_mgr.status_code == 200

    def test_manual_stock_adjustment_validation_and_ledger(
        self, test_setup, auth_client_warehouse, warehouse_user
    ):
        """اعتبارسنجی مقادیر انبارگردانی و ثبت صحیح سند در دفتر گردش انبار"""
        tire = test_setup['tire']
        url = reverse('tire-adjust-stock', args=[tire.pk])

        # ۱. مقدار منفی
        res_neg = auth_client_warehouse.post(url, {'counted_quantity': -3, 'reason': 'تست'})
        assert res_neg.status_code == 400

        # ۲. دلیل خالی
        res_no_reason = auth_client_warehouse.post(url, {'counted_quantity': 25, 'reason': '  '})
        assert res_no_reason.status_code == 400

        # ۳. بدون تغییر نسبت به موجودی فعلی
        res_same = auth_client_warehouse.post(url, {'counted_quantity': 20, 'reason': 'شمارش مجدد بدون تغییر'})
        assert res_same.status_code == 400

        # ۴. مازاد موجودی انبار (+4)
        res_surplus = auth_client_warehouse.post(
            url, {'counted_quantity': 24, 'reason': 'شمارش پایان فصل - مازاد ۴ حلقه'}
        )
        assert res_surplus.status_code == 200
        assert res_surplus.data['difference'] == 4
        assert res_surplus.data['current_stock'] == 24

        tire.refresh_from_db()
        assert tire.stock_quantity == 24

        surplus_mov = StockMovement.objects.filter(
            tire=tire,
            movement_type=StockMovementType.MANUAL_ADJUSTMENT,
            quantity=4
        ).first()
        assert surplus_mov is not None
        assert surplus_mov.balance_after == 24
        assert surplus_mov.user == warehouse_user
        assert 'مازاد' in surplus_mov.description

        # ۵. کسری موجودی انبار (-6)
        res_deficit = auth_client_warehouse.post(
            url, {'counted_quantity': 18, 'reason': 'کسری کشف‌شده در بازرسی'}
        )
        assert res_deficit.status_code == 200
        assert res_deficit.data['difference'] == -6
        assert res_deficit.data['current_stock'] == 18

        tire.refresh_from_db()
        assert tire.stock_quantity == 18

        deficit_mov = StockMovement.objects.filter(
            tire=tire,
            movement_type=StockMovementType.MANUAL_ADJUSTMENT,
            quantity=-6
        ).first()
        assert deficit_mov is not None
        assert deficit_mov.balance_after == 18

    def test_stock_movements_api_is_strictly_read_only(
        self, test_setup, auth_client_manager
    ):
        """اندپوینت‌های گردش انبار کاملاً فقط‌خواندنی هستند و ایجاد، تغییر یا حذف مستقیم ممنوع است"""
        tire = test_setup['tire']
        list_url = reverse('stock-movement-list')
        movement = StockMovement.objects.filter(tire=tire).first()
        detail_url = reverse('stock-movement-detail', args=[movement.pk])

        # خواندن مجاز است
        assert auth_client_manager.get(list_url).status_code == 200
        assert auth_client_manager.get(detail_url).status_code == 200

        # ایجاد مستقیم مسدود است (405)
        res_post = auth_client_manager.post(list_url, {
            'tire': tire.pk, 'quantity': 10, 'movement_type': 'MANUAL_ADJUSTMENT'
        })
        assert res_post.status_code == 405

        # ویرایش مسدود است (405)
        res_put = auth_client_manager.put(detail_url, {'quantity': 99})
        assert res_put.status_code == 405
        res_patch = auth_client_manager.patch(detail_url, {'quantity': 99})
        assert res_patch.status_code == 405

        # حذف مسدود است (405)
        res_delete = auth_client_manager.delete(detail_url)
        assert res_delete.status_code == 405

    def test_stock_movements_api_hides_unit_cost_from_technician(
        self, test_setup, auth_client_manager, auth_client_warehouse, auth_client_technician
    ):
        """تکنسین به API لجر انبار اصلاً دسترسی ندارد (403)، و برای انباردار بهای تمام‌شده ماسک می‌شود"""
        list_url = reverse('stock-movement-list')

        # ۱. تکنسین به لجر انبار دسترسی ندارد و خطای 403 دریافت می‌کند
        res_tech = auth_client_technician.get(list_url)
        assert res_tech.status_code == 403

        # ۲. انباردار دسترسی دارد اما unit_cost برای او ماسک است
        res_wh = auth_client_warehouse.get(list_url)
        assert res_wh.status_code == 200
        assert len(res_wh.data['results']) > 0
        assert 'unit_cost' not in res_wh.data['results'][0]

        # ۳. مدیر دسترسی دارد و فیلد unit_cost برای او نمایان است
        res_mgr = auth_client_manager.get(list_url)
        assert res_mgr.status_code == 200
        assert len(res_mgr.data['results']) > 0
        assert 'unit_cost' in res_mgr.data['results'][0]

    def test_reconcile_stock_command(self, test_setup):
        """دستور مدیریتی reconcile_stock در حالت انطباق موفق و در صورت مغایرت خطا می‌دهد"""
        # ۱. در حالت عادی با داده‌های منظم باید بدون خطا خاتمه یابد
        call_command('reconcile_stock')

        # ۲. ایجاد مغایرت مصنوعی مستقیم در دیتابیس بدون ثبت گردش
        tire = test_setup['tire']
        Tire.objects.filter(pk=tire.pk).update(stock_quantity=999)

        # باید با CommandError متوقف شود و مغایرت را اعلام کند
        with pytest.raises(CommandError) as exc_info:
            call_command('reconcile_stock')
        assert "مغایرت موجودی یافت شد" in str(exc_info.value)

    def test_record_stock_movements_accumulates_same_tire_and_detects_deficit(
        self, test_setup, manager_user
    ):
        """اگر یک تایر در یک دسته گردش انبار چند بار تکرار شود، تعدادها تجمیع شده و کسری به درستی تشخیص داده می‌شود"""
        from apps.catalog.services import record_stock_movements
        tire = test_setup['tire']  # stock_quantity = 20

        # ۱. تجمیع دو گردش خروج که مجموعاً بیشتر از موجودی است (۱۲ + ۱۰ = ۲۲ > ۲۰)
        with pytest.raises(ValidationError) as exc_info:
            record_stock_movements([
                {
                    'tire_id': tire.pk,
                    'quantity_delta': -12,
                    'movement_type': StockMovementType.SALE,
                },
                {
                    'tire_id': tire.pk,
                    'quantity_delta': -10,
                    'movement_type': StockMovementType.SALE,
                }
            ], user=manager_user)
        assert "کافی نیست" in str(exc_info.value)
        tire.refresh_from_db()
        assert tire.stock_quantity == 20  # بدون تغییر باقی می‌ماند

        # ۲. تجمیع دو گردش خروج که مجموعاً در محدوده موجودی است (۸ + ۷ = ۱۵ <= ۲۰)
        movements = record_stock_movements([
            {
                'tire_id': tire.pk,
                'quantity_delta': -8,
                'movement_type': StockMovementType.SALE,
            },
            {
                'tire_id': tire.pk,
                'quantity_delta': -7,
                'movement_type': StockMovementType.SALE,
            }
        ], user=manager_user)
        assert len(movements) == 2
        tire.refresh_from_db()
        assert tire.stock_quantity == 5  # 20 - 15 = 5
        assert movements[0].balance_after == 12
        assert movements[1].balance_after == 5

