from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Brand, Size, StockMovement, StockMovementType, Tire
from apps.customers.models import Customer
from apps.finance.models import ReceiptVoucher
from apps.finance.services import create_receipt_voucher_service, sync_sales_invoice_payment_status
from apps.invoices.models import InvoiceStatus, PaymentStatus, SalesInvoice
from apps.invoices.services import confirm_sales_invoice_service, create_sales_invoice_service


@pytest.fixture
def parts(db, manager_user):
    tire = Tire.objects.create(
        tire_name='تایر تست پیش‌نویس مالی',
        brand=Brand.objects.create(brand_name='برند پیش‌نویس مالی'),
        size=Size.objects.create(size_name='225/45R17'),
        stock_quantity=20,
        purchase_price=Decimal('1000000.00'),
        sale_price=Decimal('1500000.00'),
    )
    StockMovement.objects.create(
        tire=tire, quantity=20, movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=20, unit_cost=Decimal('1000000.00'), user=manager_user, description='موجودی اولیه',
    )
    customer = Customer.objects.create(full_name='مشتری پیش‌نویس مالی', phone_number='09127778899')
    return {'tire': tire, 'customer': customer}


def _draft(parts, user):
    return create_sales_invoice_service(
        customer=parts['customer'], vehicle=None,
        tire_items_data=[{'tire': parts['tire'], 'quantity': 2}],
        service_items_data=[], status=InvoiceStatus.DRAFT, created_by=user,
    )


@pytest.mark.django_db
class TestReceiptsRequireConfirmedInvoice:

    def test_create_draft_with_paid_status_rejected_via_api(self, auth_client_manager, parts):
        response = auth_client_manager.post(reverse('sales-invoice-list'), {
            'customer': parts['customer'].pk,
            'status': InvoiceStatus.DRAFT,
            'payment_status': PaymentStatus.PAID,
            'tire_items': [{'tire': parts['tire'].pk, 'quantity': 1}],
        }, format='json')
        assert response.status_code == 400
        assert 'payment_status' in response.data['errors']
        assert not SalesInvoice.objects.exists()
        assert not ReceiptVoucher.objects.exists()

    def test_create_draft_with_paid_status_rejected_in_service(self, parts, manager_user):
        with pytest.raises(ValidationError):
            create_sales_invoice_service(
                customer=parts['customer'], vehicle=None,
                tire_items_data=[{'tire': parts['tire'], 'quantity': 1}],
                service_items_data=[], status=InvoiceStatus.DRAFT,
                payment_status=PaymentStatus.PAID, created_by=manager_user,
            )
        assert not SalesInvoice.objects.exists()

    def test_receipt_service_rejects_draft_invoice(self, parts, manager_user):
        draft = _draft(parts, manager_user)
        with pytest.raises(ValidationError):
            create_receipt_voucher_service(sales_invoice=draft, amount=Decimal('1000.00'), user=manager_user)
        assert not ReceiptVoucher.objects.exists()

    def test_receipt_service_rechecks_status_under_lock(self, parts, manager_user):
        stale = create_sales_invoice_service(
            customer=parts['customer'], vehicle=None,
            tire_items_data=[{'tire': parts['tire'], 'quantity': 1}],
            service_items_data=[], created_by=manager_user,
        )
        SalesInvoice.objects.filter(pk=stale.pk).update(status=InvoiceStatus.DRAFT)
        assert stale.status == InvoiceStatus.CONFIRMED
        with pytest.raises(ValidationError):
            create_receipt_voucher_service(sales_invoice=stale, amount=Decimal('1000.00'), user=manager_user)

    def test_receipt_endpoint_rejects_draft_invoice(self, auth_client_manager, parts, manager_user):
        draft = _draft(parts, manager_user)
        response = auth_client_manager.post(reverse('receipt-voucher-list'), {
            'sales_invoice': draft.pk, 'amount': '1000.00',
        }, format='json')
        assert response.status_code == 400
        assert 'sales_invoice' in response.data['errors']
        assert not ReceiptVoucher.objects.exists()

    def test_draft_can_be_confirmed_then_paid(self, auth_client_manager, parts, manager_user):
        draft = _draft(parts, manager_user)
        confirm_sales_invoice_service(draft, user=manager_user)

        response = auth_client_manager.post(reverse('receipt-voucher-list'), {
            'sales_invoice': draft.pk, 'amount': '3000000.00',
        }, format='json')
        assert response.status_code == 201, response.data
        draft.refresh_from_db()
        assert draft.status == InvoiceStatus.CONFIRMED
        assert draft.payment_status == PaymentStatus.PAID

    def test_sync_leaves_unpaid_draft_unpaid(self, parts, manager_user):
        draft = _draft(parts, manager_user)
        assert sync_sales_invoice_payment_status(draft) == PaymentStatus.UNPAID
        confirm_sales_invoice_service(draft, user=manager_user)
        draft.refresh_from_db()
        assert draft.payment_status == PaymentStatus.UNPAID

    def test_paid_confirmed_invoice_still_creates_receipt(self, parts, manager_user):
        invoice = create_sales_invoice_service(
            customer=parts['customer'], vehicle=None,
            tire_items_data=[{'tire': parts['tire'], 'quantity': 1}],
            service_items_data=[], payment_status=PaymentStatus.PAID, created_by=manager_user,
        )
        assert invoice.payment_status == PaymentStatus.PAID
        assert ReceiptVoucher.objects.filter(sales_invoice=invoice).count() == 1
