import io
import pytest
from decimal import Decimal
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer
from apps.suppliers.models import Supplier
from apps.invoices.models import PaymentStatus
from apps.invoices.services import create_sales_invoice_service, create_purchase_invoice_service
from apps.finance.services import create_receipt_voucher_service, create_payment_voucher_service


@pytest.fixture
def setup_reconcile_data(db, manager_user):
    brand = Brand.objects.create(brand_name='بارز رکونسایل')
    size = Size.objects.create(size_name='175/70R13')
    tire = Tire.objects.create(
        tire_name='بارز ۱۳',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('400000.00'),
        sale_price=Decimal('600000.00'),
        min_stock_alert=2
    )
    StockMovement.objects.create(
        tire=tire,
        quantity=20,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=20,
        unit_cost=Decimal('400000.00'),
        user=manager_user,
        description='موجودی اولیه'
    )
    customer = Customer.objects.create(full_name='رضا علوی', phone_number='09121112233')
    supplier = Supplier.objects.create(supplier_name='پخش تایر البرز', phone_number='02633334444')
    return {
        'tire': tire,
        'customer': customer,
        'supplier': supplier,
        'manager': manager_user
    }


@pytest.mark.django_db
class TestReconcilePaymentsCommand:

    def test_reconcile_payments_clean_database_success(self, setup_reconcile_data):
        """تطبیق موفق در صورتی که هیچ مغایرتی وجود نداشته باشد"""
        out = io.StringIO()
        call_command('reconcile_payments', stdout=out)
        output = out.getvalue()
        assert '۰ مغایرت' in output
        assert 'کاملاً منطبق است' in output

    def test_reconcile_payments_detects_sales_invoice_discrepancy(self, setup_reconcile_data):
        """تشخیص مغایرت وضعیت فاکتور فروش و خروج با خطای CommandError"""
        data = setup_reconcile_data
        inv = create_sales_invoice_service(
            customer=data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_price': Decimal('600000.00')}],
            service_items_data=[],
            created_by=data['manager']
        )
        # وضعیت ذخیره‌شده UNPAID است. عمداً وضعیت ذخیره‌شده را به PAID تغییر می‌دهیم بدون سند دریافت:
        inv.payment_status = PaymentStatus.PAID
        inv.save(update_fields=['payment_status'])

        out = io.StringIO()
        with pytest.raises(CommandError) as exc_info:
            call_command('reconcile_payments', stdout=out)

        output = out.getvalue()
        assert 'مغایرت در وضعیت پرداخت فاکتورها مشاهده شد' in output
        assert 'فروش' in output
        assert str(inv.sales_invoice_id) in output
        assert '1 مغایرت در وضعیت پرداخت یافت شد' in str(exc_info.value)

    def test_reconcile_payments_detects_purchase_invoice_discrepancy(self, setup_reconcile_data):
        """تشخیص مغایرت وضعیت فاکتور خرید و خروج با خطای CommandError"""
        data = setup_reconcile_data
        p_inv = create_purchase_invoice_service(
            supplier=data['supplier'],
            tire_items_data=[{'tire': data['tire'], 'quantity': 2, 'unit_cost': Decimal('400000.00')}],
            created_by=data['manager']
        )
        # پرداخت کامل ثبت می‌کنیم -> وضعیت PAID می‌شود
        create_payment_voucher_service(p_inv, Decimal('800000.00'), user=data['manager'])
        p_inv.refresh_from_db()
        assert p_inv.payment_status == PaymentStatus.PAID

        # عمداً وضعیت ذخیره‌شده را به UNPAID تحریف می‌کنیم
        p_inv.payment_status = PaymentStatus.UNPAID
        p_inv.save(update_fields=['payment_status'])

        out = io.StringIO()
        with pytest.raises(CommandError) as exc_info:
            call_command('reconcile_payments', stdout=out)

        output = out.getvalue()
        assert 'مغایرت در وضعیت پرداخت فاکتورها مشاهده شد' in output
        assert 'خرید' in output
        assert str(p_inv.purchase_invoice_id) in output
        assert '1 مغایرت در وضعیت پرداخت یافت شد' in str(exc_info.value)
