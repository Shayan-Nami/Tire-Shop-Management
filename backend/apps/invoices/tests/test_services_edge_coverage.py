import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User, UserRole
from apps.customers.models import Customer
from apps.catalog.models import Tire, Brand, Size, StockMovementType
from apps.services_app.models import Service
from apps.suppliers.models import Supplier
from apps.catalog.services import record_stock_movements
from apps.invoices.models import (
    PaymentStatus
)
from apps.invoices.services import (
    create_sales_invoice_service,
    create_purchase_invoice_service,
    create_sales_return_service,
)
from apps.finance.services import (
    create_receipt_voucher_service,
    cancel_receipt_voucher_service,
    create_payment_voucher_service,
    cancel_payment_voucher_service,
    create_customer_refund_voucher_service,
    cancel_customer_refund_voucher_service,
)


@pytest.fixture
def manager_user(db):
    return User.objects.create_user(
        username='manager_edge_cov',
        password='Password123!',
        role=UserRole.MANAGER,
        full_name='مدیر پوشش کامل'
    )


@pytest.fixture
def customer_obj(db):
    return Customer.objects.create(full_name='مشتری تست پوشش', phone_number='09120001122')


@pytest.fixture
def supplier_obj(db):
    return Supplier.objects.create(supplier_name='تأمین‌کننده تست پوشش', phone_number='02188887766')


@pytest.fixture
def brand_sample(db):
    return Brand.objects.create(brand_name='بارز پوشش')


@pytest.fixture
def size_sample(db):
    return Size.objects.create(size_name='205/55R16 پوشش')


@pytest.fixture
def tire_sample(db, brand_sample, size_sample):
    return Tire.objects.create(
        tire_name='تایر تست پوشش ۲۰۵/۵۵R۱۶',
        size=size_sample,
        brand=brand_sample,
        stock_quantity=10,
        purchase_price=Decimal('1000000'),
        sale_price=Decimal('1500000')
    )


@pytest.fixture
def service_sample(db):
    return Service.objects.create(
        service_name='بالانس روکار',
        price=Decimal('100000'),
        description='تست'
    )


@pytest.mark.django_db
class TestServicesComprehensiveEdgeCoverage:

    # ------------------ Catalog Services ------------------
    def test_catalog_service_empty_and_zero_delta(self, brand_sample, size_sample):
        assert record_stock_movements([]) == []

        # delta == 0
        t = Tire.objects.create(
            tire_name='تایر دلتا صفر', size=size_sample, brand=brand_sample,
            stock_quantity=5, purchase_price=Decimal('100'), sale_price=Decimal('200')
        )
        res = record_stock_movements([{'tire_id': t.pk, 'quantity_delta': 0, 'movement_type': StockMovementType.INITIAL_STOCK}])
        assert res == []

    def test_catalog_service_non_existent_tire_id(self):
        with pytest.raises(ValidationError) as exc:
            record_stock_movements([{'tire_id': 999999, 'quantity_delta': 1, 'movement_type': StockMovementType.INITIAL_STOCK}])
        assert 'یافت نشد' in str(exc.value)

    # ------------------ Invoices Services: Sales ------------------
    def test_sales_invoice_duplicate_tire_raises_error(self, customer_obj, tire_sample, manager_user):
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer_obj,
                vehicle=None,
                tire_items_data=[
                    {'tire': tire_sample, 'quantity': 1},
                    {'tire': tire_sample, 'quantity': 2}
                ],
                service_items_data=[],
                created_by=manager_user
            )
        assert 'تایر تکراری' in str(exc.value)

    def test_sales_invoice_duplicate_service_raises_error(self, customer_obj, tire_sample, service_sample, manager_user):
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer_obj,
                vehicle=None,
                tire_items_data=[{'tire': tire_sample, 'quantity': 1}],
                service_items_data=[
                    {'service': service_sample, 'quantity': 1},
                    {'service': service_sample, 'quantity': 1}
                ],
                created_by=manager_user
            )
        assert 'خدمت تکراری' in str(exc.value)

    def test_sales_invoice_invalid_discounts(self, customer_obj, tire_sample, manager_user):
        # درصد تخفیف منفی
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer_obj, vehicle=None,
                tire_items_data=[{'tire': tire_sample, 'quantity': 1}],
                service_items_data=[], discount_percent=-5, created_by=manager_user
            )
        assert 'درصد تخفیف' in str(exc.value)

        # درصد تخفیف بالای ۱۰۰
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer_obj, vehicle=None,
                tire_items_data=[{'tire': tire_sample, 'quantity': 1}],
                service_items_data=[], discount_percent=105, created_by=manager_user
            )
        assert 'درصد تخفیف' in str(exc.value)

        # مبلغ تخفیف منفی
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer_obj, vehicle=None,
                tire_items_data=[{'tire': tire_sample, 'quantity': 1}],
                service_items_data=[], discount_amount=-1000, created_by=manager_user
            )
        assert 'مبلغ تخفیف' in str(exc.value)

        # تخفیف هم‌زمان مبلغی و درصدی
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer_obj, vehicle=None,
                tire_items_data=[{'tire': tire_sample, 'quantity': 1}],
                service_items_data=[], discount_amount=1000, discount_percent=10, created_by=manager_user
            )
        assert 'تخفیف' in str(exc.value) and ('درصدی' in str(exc.value) or 'مبلغی' in str(exc.value))

    def test_sales_invoice_invalid_item_quantities_and_prices(self, customer_obj, tire_sample, manager_user):
        # تعداد صفر یا منفی
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer_obj, vehicle=None,
                tire_items_data=[{'tire': tire_sample, 'quantity': 0}],
                service_items_data=[], created_by=manager_user
            )
        assert 'بزرگتر از صفر باشد' in str(exc.value)

        # قیمت واحد منفی
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer_obj, vehicle=None,
                tire_items_data=[{'tire': tire_sample, 'quantity': 1, 'unit_price': -500}],
                service_items_data=[], created_by=manager_user
            )
        assert 'منفی باشد' in str(exc.value)

    def test_sales_invoice_with_service_items_and_zero_total(self, customer_obj, service_sample, manager_user):
        # فاکتور خدمات با تخفیف ۱۰۰ درصدی -> مبلغ کل صفر -> وضعیت پرداخت خودکار PAID
        inv = create_sales_invoice_service(
            customer=customer_obj,
            vehicle=None,
            tire_items_data=[],
            service_items_data=[{'service': service_sample, 'quantity': 2, 'unit_price': Decimal('50000')}],
            discount_percent=100,
            created_by=manager_user
        )
        assert inv.total_amount == Decimal('0.00')
        assert inv.payment_status == PaymentStatus.PAID
        assert inv.service_items.count() == 1

    # ------------------ Invoices Services: Purchase ------------------
    def test_purchase_invoice_duplicate_tire_raises_error(self, supplier_obj, tire_sample, manager_user):
        with pytest.raises(ValidationError) as exc:
            create_purchase_invoice_service(
                supplier=supplier_obj,
                tire_items_data=[
                    {'tire': tire_sample, 'quantity': 1, 'unit_cost': Decimal('100000')},
                    {'tire': tire_sample, 'quantity': 2, 'unit_cost': Decimal('100000')}
                ],
                created_by=manager_user
            )
        assert 'تایر تکراری' in str(exc.value)

    def test_purchase_invoice_invalid_quantity_and_cost(self, supplier_obj, tire_sample, manager_user):
        with pytest.raises(ValidationError) as exc:
            create_purchase_invoice_service(
                supplier=supplier_obj,
                tire_items_data=[{'tire': tire_sample, 'quantity': 0, 'unit_cost': Decimal('100000')}],
                created_by=manager_user
            )
        assert 'مثبت باشد' in str(exc.value) or 'بزرگتر از صفر باشد' in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            create_purchase_invoice_service(
                supplier=supplier_obj,
                tire_items_data=[{'tire': tire_sample, 'quantity': 1, 'unit_cost': Decimal('-100')}],
                created_by=manager_user
            )
        assert 'منفی باشد' in str(exc.value)

    # ------------------ Invoices Services: Sales Return ------------------
    def test_sales_return_edge_validations(self, customer_obj, tire_sample, service_sample, manager_user):
        inv = create_sales_invoice_service(
            customer=customer_obj, vehicle=None,
            tire_items_data=[{'tire': tire_sample, 'quantity': 2, 'unit_price': Decimal('1500000')}],
            service_items_data=[{'service': service_sample, 'quantity': 1, 'unit_price': Decimal('100000')}],
            discount_amount=Decimal('100000'),
            created_by=manager_user
        )
        ti = inv.tire_items.first()

        # شرح خالی
        with pytest.raises(ValidationError) as exc:
            create_sales_return_service(inv, [{'sales_invoice_tire_item_id': ti.pk, 'quantity': 1}], reason='', user=manager_user)
        assert 'علت / شرح مرجوعی' in str(exc.value)

        # اقلام خالی
        with pytest.raises(ValidationError) as exc:
            create_sales_return_service(inv, [], reason='شرح تست', user=manager_user)
        assert 'حداقل یک قلم تایر' in str(exc.value)

        # تاریخ در آینده
        future_date = timezone.now() + timedelta(days=2)
        with pytest.raises(ValidationError) as exc:
            create_sales_return_service(inv, [{'sales_invoice_tire_item_id': ti.pk, 'quantity': 1}], reason='تست', return_date=future_date, user=manager_user)
        assert 'در آینده باشد' in str(exc.value)

        # شناسه قلم نامعتبر یا گم‌شده
        with pytest.raises(ValidationError) as exc:
            create_sales_return_service(inv, [{'quantity': 1}], reason='تست', user=manager_user)
        assert 'sales_invoice_tire_item_id' in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            create_sales_return_service(inv, [{'sales_invoice_tire_item_id': 99999, 'quantity': 1}], reason='تست', user=manager_user)
        assert 'یافت نشد' in str(exc.value)

        # تعداد مرجوعی صفر
        with pytest.raises(ValidationError) as exc:
            create_sales_return_service(inv, [{'sales_invoice_tire_item_id': ti.pk, 'quantity': 0}], reason='تست', user=manager_user)
        assert 'بزرگتر از صفر باشد' in str(exc.value)

    # ------------------ Finance Services: Receipt Voucher ------------------
    def test_receipt_voucher_edge_validations(self, customer_obj, tire_sample, manager_user):
        inv = create_sales_invoice_service(
            customer=customer_obj, vehicle=None,
            tire_items_data=[{'tire': tire_sample, 'quantity': 1, 'unit_price': Decimal('1000000')}],
            service_items_data=[], created_by=manager_user
        )

        # مبلغ منفی یا صفر
        with pytest.raises(ValidationError) as exc:
            create_receipt_voucher_service(inv, amount=Decimal('0'))
        assert 'باید بزرگتر از صفر باشد' in str(exc.value)

        # ثبت با تاریخ دلخواه
        past_date = timezone.now() - timedelta(days=1)
        voucher = create_receipt_voucher_service(inv, amount=Decimal('500000'), receipt_date=past_date, user=manager_user)
        assert voucher.receipt_date == past_date

        # ابطال با شرح خالی
        with pytest.raises(ValidationError) as exc:
            cancel_receipt_voucher_service(voucher, reason='   ')
        assert 'ثبت علت ابطال سند الزامی است' in str(exc.value)

        # ابطال موفق
        cancel_receipt_voucher_service(voucher, reason='ابطال صحیح', user=manager_user)

        # ابطال مجدد سند لغو شده
        with pytest.raises(ValidationError) as exc:
            cancel_receipt_voucher_service(voucher, reason='تکرار ابطال')
        assert 'قبلاً ابطال شده است' in str(exc.value)

    # ------------------ Finance Services: Payment Voucher ------------------
    def test_payment_voucher_edge_validations(self, supplier_obj, tire_sample, manager_user):
        p_inv = create_purchase_invoice_service(
            supplier=supplier_obj,
            tire_items_data=[{'tire': tire_sample, 'quantity': 2, 'unit_cost': Decimal('500000')}],
            created_by=manager_user
        )

        # مبلغ بزرگتر از مانده
        with pytest.raises(ValidationError) as exc:
            create_payment_voucher_service(p_inv, amount=Decimal('1500000'), user=manager_user)
        assert 'بیشتر باشد' in str(exc.value)

        # پرداخت با تاریخ سفارشی
        past_dt = timezone.now() - timedelta(hours=5)
        pv = create_payment_voucher_service(p_inv, amount=Decimal('1000000'), payment_date=past_dt, user=manager_user)
        assert pv.payment_date == past_dt
        p_inv.refresh_from_db()
        assert p_inv.payment_status == PaymentStatus.PAID

        # ثبت پرداخت مجدد وقتی تسویه شده
        with pytest.raises(ValidationError) as exc:
            create_payment_voucher_service(p_inv, amount=Decimal('100000'), user=manager_user)
        assert 'سقف مبلغ کل فاکتور' in str(exc.value)

        # ابطال با دلیل خالی
        with pytest.raises(ValidationError) as exc:
            cancel_payment_voucher_service(pv, reason='')
        assert 'ثبت علت ابطال سند الزامی است' in str(exc.value)

        # ابطال سند پرداخت
        cancel_payment_voucher_service(pv, reason='علت موجه', user=manager_user)

        # تلاش برای ابطال مجدد
        with pytest.raises(ValidationError) as exc:
            cancel_payment_voucher_service(pv, reason='دوباره')
        assert 'قبلاً ابطال شده است' in str(exc.value)

    # ------------------ Finance Services: Customer Refund Voucher ------------------
    def test_customer_refund_voucher_edge_validations(self, customer_obj, tire_sample, manager_user):
        inv = create_sales_invoice_service(
            customer=customer_obj, vehicle=None,
            tire_items_data=[{'tire': tire_sample, 'quantity': 2, 'unit_price': Decimal('500000')}],
            service_items_data=[], created_by=manager_user
        )
        create_receipt_voucher_service(inv, amount=Decimal('1000000'), user=manager_user)
        ti = inv.tire_items.first()
        ret = create_sales_return_service(
            invoice=inv,
            reason='مرجوعی برای تست استرداد',
            items_data=[{'sales_invoice_tire_item_id': ti.pk, 'quantity': 1}],
            user=manager_user
        )

        # مبلغ منفی یا صفر برای استرداد
        with pytest.raises(ValidationError) as exc:
            create_customer_refund_voucher_service(inv, amount=Decimal('-500'))
        assert 'باید بزرگتر از صفر باشد' in str(exc.value)

        # سند مرجوعی متعلق به فاکتور دیگر
        inv2 = create_sales_invoice_service(
            customer=customer_obj, vehicle=None,
            tire_items_data=[{'tire': tire_sample, 'quantity': 1, 'unit_price': Decimal('500000')}],
            service_items_data=[], created_by=manager_user
        )
        with pytest.raises(ValidationError) as exc:
            create_customer_refund_voucher_service(inv2, amount=Decimal('100000'), sales_return=ret, user=manager_user)
        assert 'متعلق به این فاکتور فروش نیست' in str(exc.value)

        # ثبت با تاریخ سفارشی
        past_dt = timezone.now() - timedelta(hours=2)
        refund_v = create_customer_refund_voucher_service(
            inv, amount=Decimal('500000'), sales_return=ret, refund_date=past_dt, user=manager_user
        )
        assert refund_v.refund_date == past_dt

        # ابطال با شرح خالی
        with pytest.raises(ValidationError) as exc:
            cancel_customer_refund_voucher_service(refund_v, reason='')
        assert 'ثبت علت ابطال سند الزامی است' in str(exc.value)

        # ابطال موفق
        cancel_customer_refund_voucher_service(refund_v, reason='ابطال استرداد', user=manager_user)

        # ابطال مجدد
        with pytest.raises(ValidationError) as exc:
            cancel_customer_refund_voucher_service(refund_v, reason='تکرار ابطال')
        assert 'قبلاً ابطال شده است' in str(exc.value)
