from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.models import Brand, Size, StockMovement, StockMovementType, Tire
from apps.customers.models import Customer
from apps.finance.models import ReceiptVoucher
from apps.invoices.models import InvoiceStatus, PaymentStatus, SalesInvoice
from apps.invoices.services import create_sales_invoice_service
from apps.services_app.models import Service

TIRE_PRICE = Decimal('1500000.00')
SERVICE_PRICE = Decimal('200000.00')


@pytest.fixture
def catalog(db, manager_user):
    tire = Tire.objects.create(
        tire_name='تایر تست سیاست قیمت',
        brand=Brand.objects.create(brand_name='برند سیاست قیمت'),
        size=Size.objects.create(size_name='195/65R15'),
        stock_quantity=50,
        purchase_price=Decimal('1000000.00'),
        sale_price=TIRE_PRICE,
    )
    StockMovement.objects.create(
        tire=tire, quantity=50, movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=50, unit_cost=Decimal('1000000.00'), user=manager_user, description='موجودی اولیه',
    )
    service = Service.objects.create(service_name='بالانس چرخ', price=SERVICE_PRICE)
    customer = Customer.objects.create(full_name='مشتری سیاست قیمت', phone_number='09123334455')
    return {'tire': tire, 'service': service, 'customer': customer}


def _payload(catalog, **overrides):
    payload = {
        'customer': catalog['customer'].pk,
        'tire_items': [{'tire': catalog['tire'].pk, 'quantity': 1}],
    }
    payload.update(overrides)
    return payload


def _post(client, payload):
    return client.post(reverse('sales-invoice-list'), payload, format='json')


@pytest.mark.django_db
class TestTechnicianCannotSetFinancialTerms:

    def test_technician_may_create_invoice_at_catalog_prices(self, auth_client_technician, catalog):
        payload = _payload(
            catalog,
            tire_items=[{'tire': catalog['tire'].pk, 'quantity': 2, 'unit_price': '1500000.00'}],
            service_items=[{'service': catalog['service'].pk, 'quantity': 1, 'unit_price': '200000.00'}],
            payment_status=PaymentStatus.UNPAID,
            discount_amount=0,
            discount_percent=0,
        )
        response = _post(auth_client_technician, payload)
        assert response.status_code == 201, response.data
        assert Decimal(response.data['total_amount']) == Decimal('3200000.00')
        assert response.data['payment_status'] == PaymentStatus.UNPAID
        assert not ReceiptVoucher.objects.exists()

    def test_technician_may_create_draft_invoice(self, auth_client_technician, catalog):
        response = _post(auth_client_technician, _payload(catalog, status=InvoiceStatus.DRAFT))
        assert response.status_code == 201, response.data
        assert response.data['status'] == InvoiceStatus.DRAFT

    def test_technician_cannot_register_paid_status(self, auth_client_technician, catalog):
        response = _post(auth_client_technician, _payload(catalog, payment_status=PaymentStatus.PAID))
        assert response.status_code == 400
        assert 'payment_status' in response.data['errors']
        assert not SalesInvoice.objects.exists()
        assert not ReceiptVoucher.objects.exists()
        catalog['tire'].refresh_from_db()
        assert catalog['tire'].stock_quantity == 50

    def test_technician_cannot_override_tire_price(self, auth_client_technician, catalog):
        payload = _payload(
            catalog,
            tire_items=[{'tire': catalog['tire'].pk, 'quantity': 1, 'unit_price': '1.00'}],
        )
        response = _post(auth_client_technician, payload)
        assert response.status_code == 400
        assert response.data['errors']['tire_items'] == [{'unit_price': [
            'تغییر قیمت واحد نسبت به قیمت کاتالوگ فقط برای مدیر سیستم مجاز است.'
        ]}]
        assert not SalesInvoice.objects.exists()

    def test_price_error_points_at_the_offending_service_row(self, auth_client_technician, catalog):
        extra = Service.objects.create(service_name='تعویض لاستیک', price=Decimal('100000.00'))
        payload = _payload(
            catalog,
            service_items=[
                {'service': catalog['service'].pk, 'quantity': 1, 'unit_price': '200000.00'},
                {'service': extra.pk, 'quantity': 1, 'unit_price': '90000.00'},
            ],
        )
        response = _post(auth_client_technician, payload)
        assert response.status_code == 400
        rows = response.data['errors']['service_items']
        assert rows[0] == {}
        assert 'unit_price' in rows[1]

    def test_technician_cannot_apply_discount(self, auth_client_technician, catalog):
        for field, value in (('discount_amount', '1000'), ('discount_percent', '10')):
            response = _post(auth_client_technician, _payload(catalog, **{field: value}))
            assert response.status_code == 400, field
            assert field in response.data['errors']
        assert not SalesInvoice.objects.exists()

    def test_service_layer_enforces_policy_for_technician(self, technician_user, catalog):
        with pytest.raises(Exception) as exc:
            create_sales_invoice_service(
                customer=catalog['customer'], vehicle=None,
                tire_items_data=[{'tire': catalog['tire'], 'quantity': 1, 'unit_price': Decimal('1')}],
                service_items_data=[], created_by=technician_user,
            )
        assert 'unit_price' in str(exc.value.detail) or 'tire_items' in str(exc.value.detail)
        assert not SalesInvoice.objects.exists()

    def test_technician_cannot_register_payment_via_other_endpoints(self, auth_client_technician, catalog, manager_user):
        invoice = create_sales_invoice_service(
            customer=catalog['customer'], vehicle=None,
            tire_items_data=[{'tire': catalog['tire'], 'quantity': 1}],
            service_items_data=[], created_by=manager_user,
        )
        response = auth_client_technician.post(reverse('receipt-voucher-list'), {
            'sales_invoice': invoice.pk, 'amount': '1000.00',
        }, format='json')
        assert response.status_code == 403
        assert not ReceiptVoucher.objects.exists()

    def test_confirming_a_technician_draft_never_records_payment(self, auth_client_technician, catalog):
        created = _post(auth_client_technician, _payload(catalog, status=InvoiceStatus.DRAFT))
        confirm = auth_client_technician.post(
            reverse('sales-invoice-confirm', kwargs={'pk': created.data['sales_invoice_id']})
        )
        assert confirm.status_code == 200
        assert confirm.data['payment_status'] == PaymentStatus.UNPAID
        assert not ReceiptVoucher.objects.exists()


@pytest.mark.django_db
class TestManagerKeepsFinancialTerms:

    def test_manager_can_override_price_discount_and_pay_at_issue(self, auth_client_manager, catalog):
        payload = _payload(
            catalog,
            tire_items=[{'tire': catalog['tire'].pk, 'quantity': 1, 'unit_price': '1400000.00'}],
            discount_percent='10',
            payment_status=PaymentStatus.PAID,
        )
        response = _post(auth_client_manager, payload)
        assert response.status_code == 201, response.data
        assert Decimal(response.data['total_amount']) == Decimal('1260000.00')
        assert response.data['payment_status'] == PaymentStatus.PAID
        assert ReceiptVoucher.objects.count() == 1

    def test_superuser_without_manager_role_is_treated_as_manager(self, catalog):
        admin = User.objects.create_superuser(username='root_tech_role', password='pass123', role=UserRole.TECHNICIAN)
        client = APIClient()
        client.force_authenticate(user=admin)
        response = _post(client, _payload(catalog, discount_amount='1000', payment_status=PaymentStatus.PAID))
        assert response.status_code == 201, response.data
