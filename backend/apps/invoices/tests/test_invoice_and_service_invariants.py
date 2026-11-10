import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib import admin
from django.core.management import call_command
from rest_framework.exceptions import ValidationError
from apps.invoices.models import (
    SalesInvoice, PurchaseInvoice, InvoiceSequence,
    InvoiceStatus, PaymentStatus
)
from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer, Vehicle
from apps.suppliers.models import Supplier
from apps.invoices.services import (
    generate_next_invoice_number, create_sales_invoice_service
)
from apps.finance.services import (
    sync_sales_invoice_payment_status, sync_purchase_invoice_payment_status
)


@pytest.fixture
def base_catalog(db):
    brand = Brand.objects.create(brand_name='بارز فیکس')
    size = Size.objects.create(size_name='185/65R14 فیکس')
    tire = Tire.objects.create(
        tire_name='بارز پریمیوم 185',
        brand=brand,
        size=size,
        stock_quantity=20,
        sale_price=Decimal('2000000.00'),
        purchase_price=Decimal('1500000.00')
    )
    supplier = Supplier.objects.create(supplier_name='تأمین‌کننده فیکس')
    customer = Customer.objects.create(full_name='مشتری تست باگ', phone_number='09120001122')
    vehicle = Vehicle.objects.create(customer=customer, license_plate='11ب222-33', model='پژو 206')
    return {
        'brand': brand, 'size': size, 'tire': tire,
        'supplier': supplier, 'customer': customer, 'vehicle': vehicle
    }


@pytest.mark.django_db
class TestInvoiceAndServiceInvariants:

    def test_generate_next_invoice_number_standalone_atomic(self):
        inv_num_sales = generate_next_invoice_number('SALES')
        assert inv_num_sales.startswith('S-')

        inv_num_purch = generate_next_invoice_number('PURCHASE')
        assert inv_num_purch.startswith('P-')

    def test_sync_payment_status_standalone_atomic(self, base_catalog, manager_user):
        inv = SalesInvoice.objects.create(
            customer=base_catalog['customer'],
            total_amount=Decimal('1000000.00'),
            created_by=manager_user
        )
        status = sync_sales_invoice_payment_status(inv)
        assert status == PaymentStatus.UNPAID

        p_inv = PurchaseInvoice.objects.create(
            supplier=base_catalog['supplier'],
            total_amount=Decimal('2000000.00'),
            created_by=manager_user
        )
        p_status = sync_purchase_invoice_payment_status(p_inv)
        assert p_status == PaymentStatus.UNPAID

    def test_sales_invoice_serializer_rejects_cancelled_and_partial(self, auth_client_manager, base_catalog):
        url = reverse('sales-invoice-list')

        res1 = auth_client_manager.post(url, {
            'customer': base_catalog['customer'].pk,
            'status': InvoiceStatus.CANCELLED,
            'tire_items': [{'tire': base_catalog['tire'].pk, 'quantity': 1}]
        }, format='json')
        assert res1.status_code == 400
        assert 'status' in str(res1.data)

        res2 = auth_client_manager.post(url, {
            'customer': base_catalog['customer'].pk,
            'payment_status': PaymentStatus.PARTIAL,
            'tire_items': [{'tire': base_catalog['tire'].pk, 'quantity': 1}]
        }, format='json')
        assert res2.status_code == 400
        assert 'payment_status' in str(res2.data)

    def test_customer_and_vehicle_permission_technician_cannot_delete(self, auth_client_technician, auth_client_manager, base_catalog):
        cust = Customer.objects.create(full_name='مشتری تست حذف', phone_number='09129998877')
        detail_url = reverse('customer-detail', kwargs={'pk': cust.pk})

        res_tech = auth_client_technician.delete(detail_url)
        assert res_tech.status_code == 403

        res_mgr = auth_client_manager.delete(detail_url)
        assert res_mgr.status_code == 204

    def test_sales_return_rejects_cross_invoice_item(self, auth_client_manager, base_catalog, manager_user):
        inv_a = create_sales_invoice_service(
            customer=base_catalog['customer'],
            vehicle=base_catalog['vehicle'],
            tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 2}],
            service_items_data=[],
            created_by=manager_user
        )
        inv_b = create_sales_invoice_service(
            customer=base_catalog['customer'],
            vehicle=base_catalog['vehicle'],
            tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 1}],
            service_items_data=[],
            created_by=manager_user
        )
        item_a = inv_a.tire_items.first()

        url = reverse('sales-return-list')
        payload = {
            'sales_invoice': inv_b.pk,
            'reason': 'تست مرجوعی نامعتبر',
            'items': [{'sales_invoice_tire_item_id': item_a.pk, 'quantity': 1}]
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert 'متعلق به فاکتور' in str(res.data)

    def test_sales_return_rejects_duplicate_item_in_same_payload(self, auth_client_manager, base_catalog, manager_user):
        inv = create_sales_invoice_service(
            customer=base_catalog['customer'],
            vehicle=base_catalog['vehicle'],
            tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 4}],
            service_items_data=[],
            created_by=manager_user
        )
        item = inv.tire_items.first()

        url = reverse('sales-return-list')
        payload = {
            'sales_invoice': inv.pk,
            'reason': 'تست اقلام تکراری',
            'items': [
                {'sales_invoice_tire_item_id': item.pk, 'quantity': 1},
                {'sales_invoice_tire_item_id': item.pk, 'quantity': 1}
            ]
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert 'تکراری' in str(res.data)

    def test_health_check_endpoint(self, api_client):
        url = reverse('health-check')
        res = api_client.get(url)
        assert res.status_code == 200
        assert res.json()['status'] == 'healthy'
        assert res.json()['database'] == 'connected'

    def test_user_self_deletion_standard_error(self, auth_client_manager, manager_user):
        url = reverse('user-detail', kwargs={'pk': manager_user.pk})
        res = auth_client_manager.delete(url)
        assert res.status_code == 400
        assert res.data['success'] is False
        assert res.data['status_code'] == 400

    def test_safe_type_conversion_in_sales_invoice(self, manager_user, base_catalog):
        with pytest.raises(ValidationError):
            create_sales_invoice_service(
                customer=base_catalog['customer'],
                vehicle=base_catalog['vehicle'],
                tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 'invalid'}],
                service_items_data=[],
                created_by=manager_user
            )

        with pytest.raises(ValidationError):
            create_sales_invoice_service(
                customer=base_catalog['customer'],
                vehicle=base_catalog['vehicle'],
                tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 1}],
                service_items_data=[],
                discount_percent='not-a-number',
                created_by=manager_user
            )

    def test_invoice_sequence_registered_in_admin(self):
        assert InvoiceSequence in admin.site._registry

    def test_reconcile_commands_run_cleanly(self):
        call_command('reconcile_stock')
        call_command('reconcile_payments')

    def test_discount_percent_model_validation(self, base_catalog, manager_user):
        inv = SalesInvoice(
            customer=base_catalog['customer'],
            discount_percent=Decimal('150.00'),
            created_by=manager_user
        )
        with pytest.raises(Exception):
            inv.full_clean()
