import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer
from apps.suppliers.models import Supplier
from apps.finance.models import PaymentVoucher
from apps.finance.serializers import ReceiptVoucherSerializer, PaymentVoucherSerializer
from apps.finance.services import create_receipt_voucher_service, create_payment_voucher_service
from apps.invoices.models import (
    InvoiceStatus
)
from apps.invoices.services import (
    create_sales_invoice_service,
    cancel_sales_invoice_service,
    create_purchase_invoice_service,
    cancel_purchase_invoice_service,
    create_sales_return_service,
)

@pytest.fixture
def setup_inventory_and_invoices(db, manager_user):
    brand = Brand.objects.create(brand_name='یزد تایر')
    size = Size.objects.create(size_name='175/70R13')
    tire = Tire.objects.create(
        tire_name='یزد تایر مرکوری',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('1500000.00'),
        sale_price=Decimal('2100000.00'),
        min_stock_alert=4
    )
    # ثبت گردش اولیه در دفتر گردش انبار
    StockMovement.objects.create(
        tire=tire,
        quantity=20,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=20,
        unit_cost=Decimal('1500000.00'),
        user=manager_user,
        description='موجودی اولیه'
    )
    customer = Customer.objects.create(
        full_name='علی رضایی',
        phone_number='09121234567'
    )
    supplier = Supplier.objects.create(
        supplier_name='توزیع تایر آسیا',
        phone_number='02177778888'
    )
    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'customer': customer,
        'supplier': supplier
    }

@pytest.mark.django_db
class TestPurchaseInvoiceCancellation:

    def test_cancel_purchase_invoice_deducts_stock_and_creates_movement(self, setup_inventory_and_invoices, manager_user):
        """لغو فاکتور خرید، موجودی را کسر کرده و سند گردش PURCHASE_CANCEL ثبت می‌کند"""
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']

        invoice = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 10, 'unit_cost': Decimal('1600000.00')}],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.stock_quantity == 30
        assert invoice.status == InvoiceStatus.CONFIRMED

        cancel_purchase_invoice_service(invoice, user=manager_user)
        invoice.refresh_from_db()
        tire.refresh_from_db()

        assert invoice.status == InvoiceStatus.CANCELLED
        assert tire.stock_quantity == 20

        cancel_movement = StockMovement.objects.filter(
            tire=tire,
            movement_type=StockMovementType.PURCHASE_CANCEL,
            purchase_invoice=invoice
        ).first()
        assert cancel_movement is not None
        assert cancel_movement.quantity == -10
        assert cancel_movement.balance_after == 20
        assert cancel_movement.user == manager_user

    def test_cancel_purchase_invoice_fails_when_insufficient_stock(self, setup_inventory_and_invoices, manager_user):
        """اگر تایر خریداری‌شده فروخته شده باشد و موجودی کمتر از تعداد خرید باشد، لغو با خطا متوقف می‌شود"""
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']
        customer = setup_inventory_and_invoices['customer']

        # خرید ۱۰ حلقه (موجودی ۲۰ + ۱۰ = ۳۰)
        purchase_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 10, 'unit_cost': Decimal('1600000.00')}],
            created_by=manager_user
        )

        # فروش ۲۵ حلقه (موجودی باقی‌مانده: ۵ حلقه)
        create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 25, 'unit_price': tire.sale_price}],
            service_items_data=[],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.stock_quantity == 5

        # تلاش برای لغو فاکتور خرید ۱۰ حلقه‌ای در حالی که فقط ۵ حلقه موجود است
        with pytest.raises(ValidationError) as exc_info:
            cancel_purchase_invoice_service(purchase_inv, user=manager_user)
        assert "کافی نیست" in str(exc_info.value)

        # تأیید عدم تغییر وضعیت و موجودی
        purchase_inv.refresh_from_db()
        tire.refresh_from_db()
        assert purchase_inv.status == InvoiceStatus.CONFIRMED
        assert tire.stock_quantity == 5

    def test_cancel_purchase_invoice_fails_if_payment_exists(self, setup_inventory_and_invoices, manager_user):
        """فاکتور خریدی که برای آن سند پرداخت وجه ثبت شده، قابل لغو نیست"""
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']

        purchase_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 5, 'unit_cost': Decimal('1600000.00')}],
            created_by=manager_user
        )
        PaymentVoucher.objects.create(
            purchase_invoice=purchase_inv,
            amount=Decimal('4000000.00')
        )

        with pytest.raises(ValidationError) as exc_info:
            cancel_purchase_invoice_service(purchase_inv, user=manager_user)
        assert "سند پرداخت وجه" in str(exc_info.value)
        purchase_inv.refresh_from_db()
        assert purchase_inv.status == InvoiceStatus.CONFIRMED

    def test_double_cancel_purchase_invoice_rejected(self, setup_inventory_and_invoices, manager_user):
        """لغو دوباره فاکتور خریدی که قبلاً لغو شده با خطا رد می‌شود"""
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']

        purchase_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_cost': Decimal('1600000.00')}],
            created_by=manager_user
        )
        cancel_purchase_invoice_service(purchase_inv, user=manager_user)

        with pytest.raises(ValidationError) as exc_info:
            cancel_purchase_invoice_service(purchase_inv, user=manager_user)
        assert "قبلاً لغو شده است" in str(exc_info.value)

    def test_purchase_price_restored_to_previous_purchase_cost_on_cancel(self, setup_inventory_and_invoices, manager_user):
        """در صورت لغو آخرین فاکتور خرید، نرخ خرید تایر به نرخ خرید فاکتور قبلی برمی‌گردد"""
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']
        tire.purchase_price = Decimal('1400000.00')
        tire.save()

        # خرید اول با قیمت ۱۵۰,۰۰۰
        create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 5, 'unit_cost': Decimal('1500000.00')}],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('1500000.00')

        # خرید دوم با قیمت ۱۸۰,۰۰۰
        p2 = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 5, 'unit_cost': Decimal('1800000.00')}],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('1800000.00')

        # لغو خرید دوم (آخرین خرید): نرخ خرید تایر باید به ۱۵۰,۰۰۰ بازگردد
        cancel_purchase_invoice_service(p2, user=manager_user)
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('1500000.00')

    def test_cancel_purchase_invoice_api_permissions(
        self, setup_inventory_and_invoices, manager_user, auth_client_manager, auth_client_warehouse, auth_client_technician
    ):
        """فقط مدیر مجاز به لغو فاکتور خرید از طریق API است (انباردار و تکنسین 403)"""
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']

        p = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_cost': Decimal('1500000.00')}],
            created_by=manager_user
        )
        url = reverse('purchase-invoice-cancel', kwargs={'pk': p.pk})

        # تکنسین 403
        assert auth_client_technician.post(url).status_code == 403
        # انباردار 403
        assert auth_client_warehouse.post(url).status_code == 403
        # مدیر 200
        res_mgr = auth_client_manager.post(url)
        assert res_mgr.status_code == 200
        p.refresh_from_db()
        assert p.status == InvoiceStatus.CANCELLED

@pytest.mark.django_db
class TestSalesReturnsAndRefunds:

    def test_partial_sales_return_restores_stock_and_calculates_amounts(self, setup_inventory_and_invoices, manager_user):
        """مرجوعی جزئی تایر: افزایش موجودی انبار، ثبت گردش SALE_RETURN و محاسبه مقادیر محاسباتی فاکتور"""
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.stock_quantity == 16
        sales_item = invoice.tire_items.first()

        # مرجوعی ۱ حلقه
        sales_return = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='نارضایتی مشتری از سایز تایر',
            user=manager_user
        )

        tire.refresh_from_db()
        invoice.refresh_from_db()
        assert tire.stock_quantity == 17
        assert sales_return.total_refund_amount == Decimal('2000000.00')

        # بررسی فیلدهای محاسباتی فاکتور فروش
        assert invoice.returned_amount == Decimal('2000000.00')
        assert invoice.net_amount == Decimal('6000000.00')  # 8,000,000 - 2,000,000

        # بررسی سند گردش انبار
        movement = StockMovement.objects.filter(
            tire=tire,
            movement_type=StockMovementType.SALE_RETURN,
            sales_invoice=invoice
        ).first()
        assert movement is not None
        assert movement.quantity == 1
        assert movement.balance_after == 17
        assert movement.unit_cost == sales_item.unit_cost
        assert movement.sales_return == sales_return

    def test_over_return_beyond_sold_quantity_rejected(self, setup_inventory_and_invoices, manager_user):
        """مرجوعی بیش از تعداد فروخته‌شده در فاکتور با خطای اعتبارسنجی رد می‌شود"""
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()

        # تلاش برای مرجوعی ۳ حلقه در حالی که ۲ حلقه فروخته شده
        with pytest.raises(ValidationError) as exc_info:
            create_sales_return_service(
                invoice=invoice,
                items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 3}],
                reason='مرجوعی مازاد',
                user=manager_user
            )
        assert "بیشتر از سقف مجاز" in str(exc_info.value)

        # مرجوعی ۲ حلقه (سقف مجاز)
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 2}],
            reason='مرجوعی کل',
            user=manager_user
        )

        # تلاش برای مرجوعی ۱ حلقه دیگر پس از تسویه مرجوعی
        with pytest.raises(ValidationError) as exc_info2:
            create_sales_return_service(
                invoice=invoice,
                items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
                reason='مرجوعی مجدد',
                user=manager_user
            )
        assert "بیشتر از سقف مجاز" in str(exc_info2.value)

    def test_cannot_cancel_sales_invoice_with_existing_returns(self, setup_inventory_and_invoices, manager_user):
        """فاکتور فروشی که دارای سند مرجوعی است قابل لغو نیست و مانع بازگشت دوبار موجودی می‌شود"""
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        # موجودی اولیه ۲۰
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.stock_quantity == 16

        sales_item = invoice.tire_items.first()
        # ۱ حلقه مرجوع می‌شود (موجودی ۱۷)
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی ۱ حلقه',
            user=manager_user
        )
        tire.refresh_from_db()
        assert tire.stock_quantity == 17

        # تلاش برای لغو فاکتور فروش باید مسدود شود تا موجودی ۴ بار دیگر برنگردد
        with pytest.raises(ValidationError) as exc_info:
            cancel_sales_invoice_service(invoice, user=manager_user)
        assert "سند مرجوعی ثبت شده" in str(exc_info.value)

        tire.refresh_from_db()
        assert tire.stock_quantity == 17  # موجودی دست‌نخورده باقی می‌ماند

    def test_refund_amount_proportionately_accounts_for_invoice_discount_percentage(
        self, setup_inventory_and_invoices, manager_user
    ):
        """لحاظ سهم تخفیف درصدی در محاسبه مبلغ استرداد و رند کردن به ریال"""
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        # ۴ حلقه به قیمت ۲,۰۰۰,۰۰۰ = ۸,۰۰۰,۰۰۰ با ۱۰٪ تخفیف درصدی -> مبلغ کل فاکتور: ۷,۲۰۰,۰۰۰
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            discount_percent=Decimal('10.00'),
            created_by=manager_user
        )
        assert invoice.total_amount == Decimal('7200000.00')
        sales_item = invoice.tire_items.first()

        # مرجوعی ۱ حلقه: مبلغ استرداد باید ۲,۰۰۰,۰۰۰ منهای ۱۰٪ تخفیف = ۱,۸۰۰,۰۰۰ ریال باشد
        sales_return = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='تست تخفیف درصدی',
            user=manager_user
        )
        assert sales_return.total_refund_amount == Decimal('1800000.00')
        assert sales_return.items.first().refund_amount == Decimal('1800000.00')

    def test_refund_amount_proportionately_accounts_for_invoice_monetary_discount(
        self, setup_inventory_and_invoices, manager_user
    ):
        """لحاظ سهم تخفیف ریالی فاکتور به نسبت اقلام و رند کردن دقیق"""
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        # ۴ حلقه به قیمت ۱,۰۰۰,۰۰۰ = ۴,۰۰۰,۰۰۰ با تخفیف ریالی ۵۰۰,۰۰۰ ریال (نسبت تخفیف: ۱۲.۵٪)
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': Decimal('1000000.00')}],
            service_items_data=[],
            discount_amount=Decimal('500000.00'),
            created_by=manager_user
        )
        assert invoice.total_amount == Decimal('3500000.00')
        sales_item = invoice.tire_items.first()

        # مرجوعی ۱ حلقه: مبلغ استرداد = ۱,۰۰۰,۰۰۰ * (۱ - ۵۰۰,۰۰۰/۴,۰۰۰,۰۰۰) = ۸۷۵,۰۰۰ ریال
        sales_return = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='تست تخفیف ریالی',
            user=manager_user
        )
        assert sales_return.total_refund_amount == Decimal('875000.00')

    def test_sales_return_api_permissions(
        self, setup_inventory_and_invoices, manager_user, auth_client_manager, auth_client_warehouse, auth_client_technician
    ):
        """ثبت مرجوعی از طریق API فقط برای نقش مدیر مجاز است (انباردار و تکنسین 403)"""
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()
        url = reverse('sales-return-list')
        payload = {
            'sales_invoice': invoice.pk,
            'reason': 'عدم انطباق سایز',
            'items': [{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}]
        }

        # تکنسین 403
        assert auth_client_technician.post(url, payload, format='json').status_code == 403
        # انباردار 403
        assert auth_client_warehouse.post(url, payload, format='json').status_code == 403
        # مدیر 201
        res_mgr = auth_client_manager.post(url, payload, format='json')
        assert res_mgr.status_code == 201
        assert res_mgr.data['total_refund_amount'] == '2000000.00'

    def test_reports_reflect_sales_returns(self, setup_inventory_and_invoices, manager_user, auth_client_manager):
        """گزارش‌های داشبورد، فروش بر اساس برند، بازه تاریخی و سودآوری مرجوعی‌ها را لحاظ می‌کنند"""
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        # صدور فاکتور فروش ۴ حلقه به قیمت ۲,۰۰۰,۰۰۰ (خرید: ۱,۵۰۰,۰۰۰ -> سود اولیه ۵۰۰,۰۰۰ در هر حلقه = ۲,۰۰۰,۰۰۰)
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()

        # مرجوعی ۱ حلقه
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='گزارش تست مرجوعی',
            user=manager_user
        )

        # ۱. تست گزارش سودآوری
        prof_url = reverse('profitability-report')
        res_prof = auth_client_manager.get(prof_url)
        assert res_prof.status_code == 200
        tire_prof = next(item for item in res_prof.data if item['tire_id'] == tire.pk)
        assert tire_prof['total_sold'] == 3  # ۴ فروخته شده منهای ۱ مرجوعی
        assert tire_prof['total_revenue'] == 6000000.0  # ۳ * ۲,۰۰۰,۰۰۰
        assert tire_prof['total_cost'] == 4500000.0     # ۳ * ۱,۵۰۰,۰۰۰
        assert tire_prof['total_profit'] == 1500000.0   # ۳ * ۵۰۰,۰۰۰

        # ۲. تست گزارش فروش بر اساس برند
        brand_url = reverse('sales-by-brand-report')
        res_brand = auth_client_manager.get(brand_url)
        assert res_brand.status_code == 200
        brand_data = next(item for item in res_brand.data if item['brand_name'] == setup_inventory_and_invoices['brand'].brand_name)
        assert brand_data['total_quantity'] == 3
        assert brand_data['total_revenue'] == 6000000.0

        # ۳. تست گزارش داشبورد
        dash_url = reverse('dashboard-stats')
        res_dash = auth_client_manager.get(dash_url)
        assert res_dash.status_code == 200
        assert res_dash.data['today_revenue'] == 6000000.0

        # ۴. تست گزارش فروش در بازه تاریخی
        date_url = reverse('sales-by-date-report')
        res_date = auth_client_manager.get(date_url)
        assert res_date.status_code == 200
        assert res_date.data['total_sales_amount'] == 6000000.0

    def test_cancel_purchase_ignores_cancelled_purchases_when_reverting_price(self, setup_inventory_and_invoices, manager_user):
        """
        در سناریوی: خرید A، خرید B، لغو A، و سپس لغو B
        هنگام لغو B نباید قیمت به نرخ فاکتور خرید A (که لغو شده) بازگردد،
        بلکه باید به آخرین خرید معتبر پیشین (موجودی اولیه) بازگردد.
        """
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']

        # خرید A با قیمت 1,700,000
        invoice_a = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 5, 'unit_cost': Decimal('1700000.00')}],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('1700000.00')

        # خرید B با قیمت 1,900,000
        invoice_b = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 5, 'unit_cost': Decimal('1900000.00')}],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('1900000.00')

        # لغو فاکتور A (فاکتور B همچنان معتبر و آخرین است، پس نرخ 1,900,000 باقی می‌ماند)
        cancel_purchase_invoice_service(invoice_a, user=manager_user)
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('1900000.00')

        # لغو فاکتور B (آخرین خرید معتبر قبل از B اکنون گردش اولیه با نرخ 1,500,000 است، نه فاکتور لغو شده A)
        cancel_purchase_invoice_service(invoice_b, user=manager_user)
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('1500000.00')

    def test_cancel_purchase_restores_explicit_zero_initial_stock_cost(self, setup_inventory_and_invoices, manager_user):
        """An explicit zero opening cost is valid history, not an unknown cost."""
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']
        StockMovement.objects.filter(tire=tire, movement_type=StockMovementType.INITIAL_STOCK).update(unit_cost=Decimal('0.00'))
        tire.purchase_price = Decimal('1450000.00')
        tire.save()

        # خرید با قیمت 1,800,000
        inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 5, 'unit_cost': Decimal('1800000.00')}],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('1800000.00')

        cancel_purchase_invoice_service(inv, user=manager_user)
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('0.00')

    def test_sales_return_multi_step_discount_rounding_drift(self, setup_inventory_and_invoices, manager_user):
        """
        مرجوعی چندنوبتی روی فاکتور دارای تخفیف:
        هنگام مرجوعی باقی‌مانده قلم، خطای گرد کردن (penny drift) نباید انباشته شود.
        مجموع کل مرجوعی‌ها باید دقیقاً برابر با سهم خالص آن قلم از فاکتور شود.
        """
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        # صدور فاکتور ۳ حلقه تایر با قیمت ۱۰۰,۰۰۰ = ۳۰۰,۰۰۰ و ۱۰,۰۰۰ تخفیف مبلغی -> مبلغ خالص: ۲۹۰,۰۰۰
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 3, 'unit_price': Decimal('100000.00')}],
            service_items_data=[],
            discount_amount=Decimal('10000.00'),
            created_by=manager_user
        )
        assert invoice.total_amount == Decimal('290000.00')
        sales_item = invoice.tire_items.first()

        # نوبت ۱: مرجوعی ۱ حلقه
        ret1 = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی قسط ۱',
            user=manager_user
        )
        assert ret1.total_refund_amount == Decimal('96666.67')

        # نوبت ۲: مرجوعی ۱ حلقه دیگر
        ret2 = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی قسط ۲',
            user=manager_user
        )
        assert ret2.total_refund_amount == Decimal('96666.67')

        # نوبت ۳: مرجوعی آخرین حلقه (۱ حلقه باقی‌مانده از ۳ حلقه)
        # سهم کل خالص ۲۹۰,۰۰۰ منهای (۹۶,۶۶۶.۶۷ + ۹۶,۶۶۶.۶۷ = ۱۹۳,۳۳۳.۳۴) = ۹۶,۶۶۶.۶۶
        ret3 = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی قسط ۳ نهایی',
            user=manager_user
        )
        assert ret3.total_refund_amount == Decimal('96666.66')

        # مجموع کل بازپرداخت‌ها دقیقاً ۲۹۰,۰۰۰.۰۰ ریال
        total_refunded = ret1.total_refund_amount + ret2.total_refund_amount + ret3.total_refund_amount
        assert total_refunded == Decimal('290000.00')
        invoice.refresh_from_db()
        assert invoice.returned_amount == Decimal('290000.00')
        assert invoice.net_amount == Decimal('0.00')

    def test_reject_vouchers_on_cancelled_invoices(self, setup_inventory_and_invoices, manager_user):
        """
        رد ثبت سند دریافت وجه روی فاکتور فروش لغو شده
        و رد ثبت سند پرداخت وجه روی فاکتور خرید لغو شده (در سطح serializer و service)
        """
        tire = setup_inventory_and_invoices['tire']
        supplier = setup_inventory_and_invoices['supplier']
        customer = setup_inventory_and_invoices['customer']

        # ۱. فاکتور خرید و لغو آن
        purchase_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal('1500000.00')}],
            created_by=manager_user
        )
        cancel_purchase_invoice_service(purchase_inv, user=manager_user)
        purchase_inv.refresh_from_db()
        assert purchase_inv.status == InvoiceStatus.CANCELLED

        # اعتبارسنجی در سریالایزر پرداخت
        pv_serializer = PaymentVoucherSerializer(data={
            'purchase_invoice': purchase_inv.pk,
            'amount': Decimal('500000.00')
        })
        assert not pv_serializer.is_valid()
        assert 'purchase_invoice' in pv_serializer.errors
        assert 'لغو شده' in str(pv_serializer.errors['purchase_invoice'])

        # اعتبارسنجی در سرویس پرداخت
        with pytest.raises(ValidationError) as exc_pay:
            create_payment_voucher_service(
                purchase_invoice=purchase_inv,
                amount=Decimal('500000.00')
            )
        assert 'لغو شده' in str(exc_pay.value)

        # ۲. فاکتور فروش و لغو آن
        sales_inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        cancel_sales_invoice_service(sales_inv, user=manager_user)
        sales_inv.refresh_from_db()
        assert sales_inv.status == InvoiceStatus.CANCELLED

        # اعتبارسنجی در سریالایزر دریافت
        rv_serializer = ReceiptVoucherSerializer(data={
            'sales_invoice': sales_inv.pk,
            'amount': Decimal('1000000.00')
        })
        assert not rv_serializer.is_valid()
        assert 'sales_invoice' in rv_serializer.errors
        assert 'لغو شده' in str(rv_serializer.errors['sales_invoice'])

        # اعتبارسنجی در سرویس دریافت
        with pytest.raises(ValidationError) as exc_rec:
            create_receipt_voucher_service(
                sales_invoice=sales_inv,
                amount=Decimal('1000000.00')
            )
        assert 'لغو شده' in str(exc_rec.value)

    def test_sales_return_date_and_n_plus_one_avoidance(
        self, setup_inventory_and_invoices, manager_user, auth_client_manager
    ):
        """
        بررسی عدم پذیرش تاریخ آینده برای مرجوعی، و بهینه‌سازی کوئری‌های returned_amount و net_amount (جلوگیری از N+1)
        """
        tire = setup_inventory_and_invoices['tire']
        customer = setup_inventory_and_invoices['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 5, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()

        # تلاش برای ثبت مرجوعی با تاریخ آینده
        future_date = (timezone.now() + timedelta(days=2)).isoformat()
        url = reverse('sales-return-list')
        payload_future = {
            'sales_invoice': invoice.pk,
            'return_date': future_date,
            'reason': 'تست تاریخ آینده',
            'items': [{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}]
        }
        res_future = auth_client_manager.post(url, payload_future, format='json')
        assert res_future.status_code == 400
        assert 'return_date' in res_future.data.get('errors', res_future.data)
        assert 'آینده' in str(res_future.data.get('errors', res_future.data))

        # ثبت ۱ مرجوعی معتبر برای فاکتور
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی معتبر',
            user=manager_user
        )

        # بررسی واکشی لیست فاکتورها از API و اطمینان از قرار گرفتن مقادیر در پاسخ
        list_url = reverse('sales-invoice-list')
        res_list = auth_client_manager.get(list_url)
        assert res_list.status_code == 200
        inv_data = next(i for i in res_list.data['results'] if i['sales_invoice_id'] == invoice.pk)
        assert Decimal(str(inv_data['returned_amount'])) == Decimal('2000000.00')
        assert Decimal(str(inv_data['net_amount'])) == Decimal('8000000.00')

        # تأیید عدم ایجاد کوئری N+1: فیلدهای annotated در کوئری‌ست لود شده‌اند
        from apps.invoices.views import SalesInvoiceViewSet
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        req = factory.get(reverse('sales-invoice-list'))
        req.user = manager_user
        view = SalesInvoiceViewSet()
        view.request = req
        annotated_inv = view.get_queryset().filter(pk=invoice.pk).first()
        assert hasattr(annotated_inv, 'returned_amount_annotated')
        assert hasattr(annotated_inv, 'net_amount_annotated')
        assert annotated_inv.returned_amount == Decimal('2000000.00')
        assert annotated_inv.net_amount == Decimal('8000000.00')

