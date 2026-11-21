import io
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Brand, Size, StockMovement, StockMovementType, Tire
from apps.customers.models import Customer
from apps.finance.models import CustomerRefundVoucher
from apps.finance.services import (
    cancel_payment_voucher_service,
    create_payment_voucher_service,
    sync_sales_invoice_payment_status,
)
from apps.invoices.models import InvoiceStatus, PaymentStatus, SalesInvoice
from apps.invoices.serializers import SalesInvoiceSerializer
from apps.invoices.services import (
    confirm_sales_invoice_service,
    create_purchase_invoice_service,
    create_sales_invoice_service,
)
from apps.services_app.models import Service
from apps.suppliers.models import Supplier

pytestmark = pytest.mark.django_db


@pytest.fixture
def audit_setup(db, manager_user):
    brand = Brand.objects.create(brand_name='کویر تایر ممیزی')
    size = Size.objects.create(size_name='205/55R16')
    tire = Tire.objects.create(
        tire_name='تایر ممیزی',
        brand=brand,
        size=size,
        stock_quantity=50,
        purchase_price=Decimal('600000.00'),
        sale_price=Decimal('1000000.00'),
        min_stock_alert=5,
    )
    StockMovement.objects.create(
        tire=tire,
        quantity=50,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=50,
        unit_cost=Decimal('600000.00'),
        user=manager_user,
        description='موجودی اولیه تست ممیزی',
    )
    service = Service.objects.create(service_name='بالانس و نصب ممیزی', price=Decimal('500000.00'))
    customer = Customer.objects.create(full_name='مشتری ممیزی', phone_number='09123334455')
    supplier = Supplier.objects.create(supplier_name='تأمین‌کننده ممیزی', phone_number='02144556677')
    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'service': service,
        'customer': customer,
        'supplier': supplier,
        'manager': manager_user,
    }


def test_zero_rial_draft_invoice_is_unpaid_and_transitions_on_confirm_service(audit_setup):
    tire = audit_setup['tire']
    customer = audit_setup['customer']
    manager = audit_setup['manager']

    draft_pct = create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000.00')}],
        service_items_data=[],
        discount_percent=Decimal('100.00'),
        status=InvoiceStatus.DRAFT,
        created_by=manager,
    )
    assert draft_pct.total_amount == Decimal('0.00')
    assert draft_pct.status == InvoiceStatus.DRAFT
    assert draft_pct.payment_status == PaymentStatus.UNPAID

    assert sync_sales_invoice_payment_status(draft_pct) == PaymentStatus.UNPAID
    draft_pct.refresh_from_db()
    assert draft_pct.payment_status == PaymentStatus.UNPAID

    confirmed_pct = confirm_sales_invoice_service(draft_pct, user=manager)
    assert confirmed_pct.status == InvoiceStatus.CONFIRMED
    assert confirmed_pct.payment_status == PaymentStatus.PAID

    draft_zero_price = create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('0.00')}],
        service_items_data=[],
        status=InvoiceStatus.DRAFT,
        created_by=manager,
    )
    assert draft_zero_price.total_amount == Decimal('0.00')
    assert draft_zero_price.payment_status == PaymentStatus.UNPAID

    confirmed_zero_price = confirm_sales_invoice_service(draft_zero_price, user=manager)
    assert confirmed_zero_price.status == InvoiceStatus.CONFIRMED
    assert confirmed_zero_price.payment_status == PaymentStatus.PAID


def test_zero_rial_draft_invoice_is_unpaid_and_transitions_on_confirm_api(audit_setup, auth_client_manager):
    tire = audit_setup['tire']
    customer = audit_setup['customer']
    list_url = reverse('sales-invoice-list')

    res_pct = auth_client_manager.post(
        list_url,
        {
            'customer': customer.pk,
            'status': InvoiceStatus.DRAFT,
            'discount_percent': '100.00',
            'tire_items': [{'tire': tire.pk, 'quantity': 1, 'unit_price': '1000000.00'}],
            'service_items': [],
        },
        format='json',
    )
    assert res_pct.status_code == 201, res_pct.data
    assert Decimal(str(res_pct.data['total_amount'])) == Decimal('0.00')
    assert res_pct.data['status'] == InvoiceStatus.DRAFT
    assert res_pct.data['payment_status'] == PaymentStatus.UNPAID

    confirm_pct = auth_client_manager.post(
        reverse('sales-invoice-confirm', kwargs={'pk': res_pct.data['sales_invoice_id']}),
        format='json',
    )
    assert confirm_pct.status_code == 200, confirm_pct.data
    assert confirm_pct.data['status'] == InvoiceStatus.CONFIRMED
    assert confirm_pct.data['payment_status'] == PaymentStatus.PAID
    assert confirm_pct.data['invoice']['payment_status'] == PaymentStatus.PAID

    res_zero = auth_client_manager.post(
        list_url,
        {
            'customer': customer.pk,
            'status': InvoiceStatus.DRAFT,
            'tire_items': [{'tire': tire.pk, 'quantity': 1, 'unit_price': '0.00'}],
            'service_items': [],
        },
        format='json',
    )
    assert res_zero.status_code == 201, res_zero.data
    assert Decimal(str(res_zero.data['total_amount'])) == Decimal('0.00')
    assert res_zero.data['status'] == InvoiceStatus.DRAFT
    assert res_zero.data['payment_status'] == PaymentStatus.UNPAID

    confirm_zero = auth_client_manager.post(
        reverse('sales-invoice-confirm', kwargs={'pk': res_zero.data['sales_invoice_id']}),
        format='json',
    )
    assert confirm_zero.status_code == 200, confirm_zero.data
    assert confirm_zero.data['status'] == InvoiceStatus.CONFIRMED
    assert confirm_zero.data['payment_status'] == PaymentStatus.PAID


def test_db_check_constraint_rejects_draft_with_paid_or_partial(audit_setup):
    customer = audit_setup['customer']

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SalesInvoice.objects.create(
                invoice_number='S-1405-90001',
                customer=customer,
                total_amount=Decimal('0.00'),
                status=InvoiceStatus.DRAFT,
                payment_status=PaymentStatus.PAID,
            )

    draft_inv = SalesInvoice.objects.create(
        invoice_number='S-1405-90002',
        customer=customer,
        total_amount=Decimal('0.00'),
        status=InvoiceStatus.DRAFT,
        payment_status=PaymentStatus.UNPAID,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SalesInvoice.objects.filter(pk=draft_inv.pk).update(payment_status=PaymentStatus.PAID)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SalesInvoice.objects.filter(pk=draft_inv.pk).update(payment_status=PaymentStatus.PARTIAL)


def test_reconcile_payments_succeeds_with_zero_rial_draft_invoices(audit_setup):
    tire = audit_setup['tire']
    customer = audit_setup['customer']
    manager = audit_setup['manager']

    create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000.00')}],
        service_items_data=[],
        discount_percent=Decimal('100.00'),
        status=InvoiceStatus.DRAFT,
        created_by=manager,
    )
    create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('0.00')}],
        service_items_data=[],
        status=InvoiceStatus.DRAFT,
        created_by=manager,
    )

    out = io.StringIO()
    call_command('reconcile_payments', stdout=out)
    assert '۰ مغایرت' in out.getvalue()


def test_sales_invoice_serializer_exposes_subtotal_and_effective_discount(audit_setup, auth_client_manager):
    tire = audit_setup['tire']
    service = audit_setup['service']
    customer = audit_setup['customer']
    manager = audit_setup['manager']

    pct_invoice = create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1000000.00')}],
        service_items_data=[{'service': service, 'quantity': 1, 'unit_price': Decimal('500000.00')}],
        discount_percent=Decimal('15.00'),
        created_by=manager,
    )
    pct_serialized = SalesInvoiceSerializer(pct_invoice).data
    assert Decimal(pct_serialized['subtotal_amount']) == Decimal('2500000.00')
    assert Decimal(pct_serialized['effective_discount_amount']) == Decimal('375000.00')
    assert Decimal(pct_serialized['total_amount']) == Decimal('2125000.00')

    amt_invoice = create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1000000.00')}],
        service_items_data=[],
        discount_amount=Decimal('300000.00'),
        created_by=manager,
    )
    res = auth_client_manager.get(reverse('sales-invoice-detail', kwargs={'pk': amt_invoice.pk}))
    assert res.status_code == 200
    assert Decimal(str(res.data['subtotal_amount'])) == Decimal('2000000.00')
    assert Decimal(str(res.data['effective_discount_amount'])) == Decimal('300000.00')
    assert Decimal(str(res.data['total_amount'])) == Decimal('1700000.00')

    large_discounted = create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('600000000000.00')}],
        service_items_data=[],
        discount_percent=Decimal('50.00'),
        created_by=manager,
    )
    large_data = SalesInvoiceSerializer(large_discounted).data
    assert Decimal(large_data['subtotal_amount']) == Decimal('1200000000000.00')
    assert Decimal(large_data['effective_discount_amount']) == Decimal('600000000000.00')
    assert Decimal(large_data['total_amount']) == Decimal('600000000000.00')


def test_sales_return_api_respects_auto_refund_and_payment_fields(audit_setup, auth_client_manager):
    tire = audit_setup['tire']
    customer = audit_setup['customer']
    manager = audit_setup['manager']
    returns_url = reverse('sales-return-list')

    inv_no_refund = create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1000000.00')}],
        service_items_data=[],
        status=InvoiceStatus.CONFIRMED,
        payment_status=PaymentStatus.PAID,
        created_by=manager,
    )
    item_1 = inv_no_refund.tire_items.get()

    res_no_refund = auth_client_manager.post(
        returns_url,
        {
            'sales_invoice': inv_no_refund.pk,
            'reason': 'مرجوعی بدون استرداد خودکار',
            'auto_refund': False,
            'items': [{'sales_invoice_tire_item_id': item_1.pk, 'quantity': 1}],
        },
        format='json',
    )
    assert res_no_refund.status_code == 201, res_no_refund.data
    assert not CustomerRefundVoucher.objects.filter(sales_invoice=inv_no_refund).exists()
    assert inv_no_refund.excess_amount == Decimal('1000000.00')

    inv_with_refund = create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1000000.00')}],
        service_items_data=[],
        status=InvoiceStatus.CONFIRMED,
        payment_status=PaymentStatus.PAID,
        created_by=manager,
    )
    item_2 = inv_with_refund.tire_items.get()

    res_with_refund = auth_client_manager.post(
        returns_url,
        {
            'sales_invoice': inv_with_refund.pk,
            'reason': 'مرجوعی با استرداد کارت به کارت',
            'auto_refund': True,
            'payment_method': 'CARD_TO_CARD',
            'reference_number': 'REF-778899',
            'items': [{'sales_invoice_tire_item_id': item_2.pk, 'quantity': 1}],
        },
        format='json',
    )
    assert res_with_refund.status_code == 201, res_with_refund.data
    voucher = CustomerRefundVoucher.objects.get(sales_invoice=inv_with_refund)
    assert voucher.amount == Decimal('1000000.00')
    assert voucher.payment_method == 'CARD_TO_CARD'
    assert voucher.reference_number == 'REF-778899'


def test_purchase_invoice_viewset_paid_and_remaining_amounts(audit_setup, auth_client_manager):
    tire = audit_setup['tire']
    supplier = audit_setup['supplier']
    manager = audit_setup['manager']

    p_inv = create_purchase_invoice_service(
        supplier=supplier,
        tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal('600000.00')}],
        created_by=manager,
    )
    detail_url = reverse('purchase-invoice-detail', kwargs={'pk': p_inv.pk})

    assert p_inv.paid_amount == Decimal('0.00')
    assert p_inv.remaining_amount == Decimal('1200000.00')

    res_unpaid = auth_client_manager.get(detail_url)
    assert res_unpaid.status_code == 200
    assert Decimal(str(res_unpaid.data['paid_amount'])) == Decimal('0.00')
    assert Decimal(str(res_unpaid.data['remaining_amount'])) == Decimal('1200000.00')

    create_payment_voucher_service(p_inv, Decimal('450000.00'), user=manager)
    res_partial = auth_client_manager.get(detail_url)
    assert res_partial.status_code == 200
    assert Decimal(str(res_partial.data['paid_amount'])) == Decimal('450000.00')
    assert Decimal(str(res_partial.data['remaining_amount'])) == Decimal('750000.00')

    v2 = create_payment_voucher_service(p_inv, Decimal('750000.00'), user=manager)
    res_paid = auth_client_manager.get(detail_url)
    assert res_paid.status_code == 200
    assert Decimal(str(res_paid.data['paid_amount'])) == Decimal('1200000.00')
    assert Decimal(str(res_paid.data['remaining_amount'])) == Decimal('0.00')

    cancel_payment_voucher_service(v2, reason='اصلاح پرداخت', user=manager)
    res_after_cancel = auth_client_manager.get(detail_url)
    assert res_after_cancel.status_code == 200
    assert Decimal(str(res_after_cancel.data['paid_amount'])) == Decimal('450000.00')
    assert Decimal(str(res_after_cancel.data['remaining_amount'])) == Decimal('750000.00')


def test_purchase_invoice_viewset_list_queries_bounded(audit_setup, auth_client_manager):
    supplier = audit_setup['supplier']
    manager = audit_setup['manager']
    list_url = reverse('purchase-invoice-list')

    counts = []
    for batch_size in (1, 5):
        for i in range(batch_size):
            extra_tire = Tire.objects.create(
                tire_name=f'تایر خرید {batch_size}-{i}',
                brand=audit_setup['brand'],
                size=audit_setup['size'],
                stock_quantity=10,
                purchase_price=Decimal('500000.00'),
                sale_price=Decimal('700000.00'),
                min_stock_alert=2,
            )
            inv = create_purchase_invoice_service(
                supplier=supplier,
                tire_items_data=[{'tire': extra_tire, 'quantity': 2, 'unit_cost': Decimal('500000.00')}],
                created_by=manager,
            )
            create_payment_voucher_service(inv, Decimal('300000.00'), user=manager)
        with CaptureQueriesContext(connection) as queries:
            res_list = auth_client_manager.get(list_url)
            assert res_list.status_code == 200
        counts.append(len(queries))
    assert counts[0] == counts[1], counts
