from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer
from apps.finance.models import CustomerRefundVoucher, PaymentVoucher, ReceiptVoucher
from apps.finance.serializers import (
    CustomerRefundVoucherSerializer,
    PaymentVoucherSerializer,
    ReceiptVoucherSerializer,
)
from apps.finance.services import (
    create_customer_refund_voucher_service,
    create_payment_voucher_service,
    create_receipt_voucher_service,
)
from apps.invoices.models import InvoiceStatus, PaymentStatus, PurchaseInvoice, SalesInvoice
from apps.invoices.services import (
    cancel_purchase_invoice_service,
    cancel_sales_invoice_service,
    create_purchase_invoice_service,
    create_sales_invoice_service,
    create_sales_return_service,
)
from apps.suppliers.models import Supplier
from utils.domain import DomainValidationError


@pytest.fixture
def finance_phase1_setup(db):
    brand = Brand.objects.create(brand_name='میشلن')
    size = Size.objects.create(size_name='215/55R17')
    tire = Tire.objects.create(
        tire_name='پریماسی ۴',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('1000.00'),
        sale_price=Decimal('1500.00'),
    )
    customer = Customer.objects.create(full_name='مشتری مالی', phone_number='09121112233')
    supplier = Supplier.objects.create(supplier_name='تامین‌کننده مالی', phone_number='09123334455')
    return {'tire': tire, 'customer': customer, 'supplier': supplier}


@pytest.mark.django_db
class TestPhase1VoucherIntegrity:
    def test_vouchers_require_confirmed_invoices_rejecting_draft_and_cancelled(
        self, finance_phase1_setup, manager_user, auth_client_manager
    ):
        tire = finance_phase1_setup['tire']
        customer = finance_phase1_setup['customer']
        supplier = finance_phase1_setup['supplier']

        draft_sale = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1500.00')}],
            service_items_data=[],
            status=InvoiceStatus.DRAFT,
            created_by=manager_user,
        )
        with pytest.raises(DomainValidationError):
            create_receipt_voucher_service(draft_sale, amount=Decimal('500.00'), user=manager_user)
        with pytest.raises(DomainValidationError):
            create_customer_refund_voucher_service(draft_sale, amount=Decimal('100.00'), user=manager_user)

        assert auth_client_manager.post(
            reverse('receipt-voucher-list'),
            {'sales_invoice': draft_sale.pk, 'amount': '500.00', 'payment_method': 'POS'},
            format='json',
        ).status_code == 400
        assert auth_client_manager.post(
            reverse('customer-refund-voucher-list'),
            {'sales_invoice': draft_sale.pk, 'amount': '100.00', 'payment_method': 'POS'},
            format='json',
        ).status_code == 400

        cancelled_sale = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1500.00')}],
            service_items_data=[],
            status=InvoiceStatus.CONFIRMED,
            created_by=manager_user,
        )
        cancel_sales_invoice_service(cancelled_sale, user=manager_user)
        with pytest.raises(DomainValidationError):
            create_receipt_voucher_service(cancelled_sale, amount=Decimal('500.00'), user=manager_user)
        with pytest.raises(DomainValidationError):
            create_customer_refund_voucher_service(cancelled_sale, amount=Decimal('100.00'), user=manager_user)

        cancelled_purchase = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_cost': Decimal('1000.00')}],
            created_by=manager_user,
        )
        cancel_purchase_invoice_service(cancelled_purchase, user=manager_user)
        PurchaseInvoice.objects.filter(pk=cancelled_purchase.pk).update(status=InvoiceStatus.DRAFT)
        cancelled_purchase.refresh_from_db()
        with pytest.raises(DomainValidationError):
            create_payment_voucher_service(cancelled_purchase, amount=Decimal('500.00'), user=manager_user)

        assert auth_client_manager.post(
            reverse('payment-voucher-list'),
            {'purchase_invoice': cancelled_purchase.pk, 'amount': '500.00', 'payment_method': 'BANK_TRANSFER'},
            format='json',
        ).status_code == 400

    def test_vouchers_reject_future_and_pre_invoice_dates(
        self, finance_phase1_setup, manager_user, auth_client_manager
    ):
        tire = finance_phase1_setup['tire']
        customer = finance_phase1_setup['customer']
        supplier = finance_phase1_setup['supplier']

        sales_inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1500.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        create_receipt_voucher_service(sales_inv, amount=Decimal('3000.00'), user=manager_user)
        sales_return = create_sales_return_service(
            invoice=sales_inv,
            items_data=[{'sales_invoice_tire_item_id': sales_inv.tire_items.get().pk, 'quantity': 1}],
            reason='ایجاد مازاد قابل استرداد',
            user=manager_user,
        )
        purchase_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_cost': Decimal('1000.00')}],
            created_by=manager_user,
        )

        future_dt = timezone.now() + timedelta(hours=2)
        before_sale_dt = sales_inv.invoice_date - timedelta(minutes=1)
        before_purchase_dt = purchase_inv.invoice_date - timedelta(minutes=1)

        with pytest.raises(DomainValidationError, match='آینده'):
            create_receipt_voucher_service(sales_inv, amount=Decimal('100.00'), receipt_date=future_dt)
        with pytest.raises(DomainValidationError, match='پیش از تاریخ صدور'):
            create_customer_refund_voucher_service(
                sales_inv, amount=Decimal('100.00'), sales_return=sales_return, refund_date=before_sale_dt
            )
        with pytest.raises(DomainValidationError, match='آینده'):
            create_customer_refund_voucher_service(
                sales_inv, amount=Decimal('100.00'), sales_return=sales_return, refund_date=future_dt
            )
        with pytest.raises(DomainValidationError, match='آینده'):
            create_payment_voucher_service(purchase_inv, amount=Decimal('100.00'), payment_date=future_dt)
        with pytest.raises(DomainValidationError, match='پیش از تاریخ صدور'):
            create_payment_voucher_service(purchase_inv, amount=Decimal('100.00'), payment_date=before_purchase_dt)

        ReceiptVoucher.objects.filter(sales_invoice=sales_inv).update(is_cancelled=True, cancellation_reason='تست')
        assert auth_client_manager.post(
            reverse('receipt-voucher-list'),
            {
                'sales_invoice': sales_inv.pk,
                'amount': '500.00',
                'payment_method': 'POS',
                'receipt_date': before_sale_dt.isoformat(),
            },
            format='json',
        ).status_code == 400
        assert auth_client_manager.post(
            reverse('receipt-voucher-list'),
            {
                'sales_invoice': sales_inv.pk,
                'amount': '500.00',
                'payment_method': 'POS',
                'receipt_date': future_dt.isoformat(),
            },
            format='json',
        ).status_code == 400
        assert auth_client_manager.post(
            reverse('payment-voucher-list'),
            {
                'purchase_invoice': purchase_inv.pk,
                'amount': '500.00',
                'payment_method': 'BANK_TRANSFER',
                'payment_date': before_purchase_dt.isoformat(),
            },
            format='json',
        ).status_code == 400
        assert auth_client_manager.post(
            reverse('customer-refund-voucher-list'),
            {
                'sales_invoice': sales_inv.pk,
                'sales_return': sales_return.pk,
                'amount': '100.00',
                'payment_method': 'CASH',
                'refund_date': future_dt.isoformat(),
            },
            format='json',
        ).status_code == 400

    def test_customer_refunds_route_and_payment_method_display_mappings(
        self, finance_phase1_setup, manager_user, auth_client_manager
    ):
        assert reverse('customer-refund-voucher-list') == '/api/v1/treasury/customer-refunds/'

        tire = finance_phase1_setup['tire']
        customer = finance_phase1_setup['customer']
        supplier = finance_phase1_setup['supplier']

        sales_inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1500.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        purchase_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal('1000.00')}],
            created_by=manager_user,
        )

        rv_transfer = create_receipt_voucher_service(
            sales_inv, amount=Decimal('1500.00'), payment_method='BANK_TRANSFER', user=manager_user
        )
        rv_legacy = create_receipt_voucher_service(
            sales_inv, amount=Decimal('1500.00'), payment_method='کارتخوان / نقدی', user=manager_user
        )
        assert ReceiptVoucherSerializer(rv_transfer).data['payment_method_display'] == 'حواله بانکی'
        assert ReceiptVoucherSerializer(rv_legacy).data['payment_method_display'] == 'کارتخوان / نقدی'

        pv_transfer = create_payment_voucher_service(
            purchase_inv, amount=Decimal('500.00'), payment_method='BANK_TRANSFER', user=manager_user
        )
        pv_legacy = create_payment_voucher_service(
            purchase_inv, amount=Decimal('500.00'), payment_method='حواله / چک', user=manager_user
        )
        assert PaymentVoucherSerializer(pv_transfer).data['payment_method_display'] == 'حواله بانکی'
        assert PaymentVoucherSerializer(pv_legacy).data['payment_method_display'] == 'حواله / چک'

        sales_return = create_sales_return_service(
            invoice=sales_inv,
            items_data=[{'sales_invoice_tire_item_id': sales_inv.tire_items.get().pk, 'quantity': 1}],
            reason='بررسی نمایش روش پرداخت استرداد',
            user=manager_user,
        )
        refund_v = CustomerRefundVoucher.objects.create(
            sales_invoice=sales_inv,
            sales_return=sales_return,
            amount=Decimal('1500.00'),
            payment_method='BANK_TRANSFER',
            created_by=manager_user,
        )
        assert CustomerRefundVoucherSerializer(refund_v).data['payment_method_display'] == 'حواله بانکی'

        api_res = auth_client_manager.post(
            reverse('payment-voucher-list'),
            {'purchase_invoice': purchase_inv.pk, 'amount': '500.00', 'payment_method': 'POS'},
            format='json',
        )
        assert api_res.status_code == 201
        assert api_res.data['payment_method_display'] == 'کارتخوان (POS)'
        assert PaymentVoucher.objects.get(pk=api_res.data['payment_id']).payment_method == 'POS'

    def test_reconcile_payments_uses_constant_queries_without_n_plus_one(
        self, finance_phase1_setup, manager_user
    ):
        tire = finance_phase1_setup['tire']
        customer = finance_phase1_setup['customer']
        supplier = finance_phase1_setup['supplier']

        for _ in range(6):
            inv = create_sales_invoice_service(
                customer=customer,
                vehicle=None,
                tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1500.00')}],
                service_items_data=[],
                created_by=manager_user,
            )
            create_receipt_voucher_service(inv, amount=Decimal('500.00'), user=manager_user)

            p_inv = create_purchase_invoice_service(
                supplier=supplier,
                tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_cost': Decimal('1000.00')}],
                created_by=manager_user,
            )
            create_payment_voucher_service(p_inv, amount=Decimal('400.00'), user=manager_user)

        out = StringIO()
        with CaptureQueriesContext(connection) as queries:
            call_command('reconcile_payments', stdout=out)

        assert len(queries) <= 5
        assert '۰ مغایرت' in out.getvalue()

        SalesInvoice.objects.filter(pk=inv.pk).update(payment_status=PaymentStatus.PAID)
        with pytest.raises(CommandError):
            call_command('reconcile_payments', stdout=StringIO())
