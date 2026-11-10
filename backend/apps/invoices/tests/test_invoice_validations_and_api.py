import pytest
from decimal import Decimal
from django.urls import reverse
from django.db.models import ProtectedError
from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer, Vehicle
from apps.suppliers.models import Supplier
from apps.services_app.models import Service
from apps.invoices.models import SalesInvoice, PurchaseInvoice
from apps.finance.models import ReceiptVoucher, PaymentVoucher

@pytest.fixture
def invoice_api_setup(db):
    brand = Brand.objects.create(brand_name='بارز تست')
    size = Size.objects.create(size_name='205/55R16')
    tire = Tire.objects.create(
        tire_name='تایر رادیال ۱۶',
        brand=brand,
        size=size,
        stock_quantity=15,
        purchase_price=Decimal('2000000'),
        sale_price=Decimal('2800000'),
        min_stock_alert=4
    )
    service = Service.objects.create(
        service_name='تعویض و بالانس',
        price=Decimal('300000'),
        description='تعویض ۴ حلقه'
    )
    customer1 = Customer.objects.create(
        full_name='رضا محمدی',
        phone_number='09121111111',
        national_code='0011223344'
    )
    customer2 = Customer.objects.create(
        full_name='سارا احمدی',
        phone_number='09122222222',
        national_code='0055667788'
    )
    vehicle1 = Vehicle.objects.create(
        customer=customer1,
        license_plate='22ب222-22',
        model='پژو ۲۰۶'
    )
    vehicle2 = Vehicle.objects.create(
        customer=customer2,
        license_plate='33ج333-33',
        model='سمند'
    )
    supplier = Supplier.objects.create(
        supplier_name='تأمین لاستیک کویر',
        phone_number='02188888888'
    )
    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'service': service,
        'customer1': customer1,
        'customer2': customer2,
        'vehicle1': vehicle1,
        'vehicle2': vehicle2,
        'supplier': supplier,
    }

@pytest.mark.django_db
class TestInvoiceAPIValidations:

    def test_delete_sales_invoice_blocked_method_not_allowed(self, auth_client_manager, invoice_api_setup):
        setup = invoice_api_setup
        create_url = reverse('sales-invoice-list')
        res_create = auth_client_manager.post(create_url, {
            'customer': setup['customer1'].pk,
            'vehicle': setup['vehicle1'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 2}]
        }, format='json')
        assert res_create.status_code == 201
        invoice_id = res_create.data['sales_invoice_id']

        delete_url = reverse('sales-invoice-detail', kwargs={'pk': invoice_id})
        res_delete = auth_client_manager.delete(delete_url)
        assert res_delete.status_code == 405

        assert SalesInvoice.objects.filter(pk=invoice_id).exists()

    def test_put_patch_sales_invoice_blocked_method_not_allowed(self, auth_client_manager, invoice_api_setup):
        setup = invoice_api_setup
        create_url = reverse('sales-invoice-list')
        res_create = auth_client_manager.post(create_url, {
            'customer': setup['customer1'].pk,
            'vehicle': setup['vehicle1'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 2}]
        }, format='json')
        assert res_create.status_code == 201
        invoice_id = res_create.data['sales_invoice_id']

        detail_url = reverse('sales-invoice-detail', kwargs={'pk': invoice_id})
        res_put = auth_client_manager.put(detail_url, {'notes': 'تغییر غیرمجاز'}, format='json')
        assert res_put.status_code == 405

        res_patch = auth_client_manager.patch(detail_url, {'notes': 'تغییر غیرمجاز'}, format='json')
        assert res_patch.status_code == 405

    def test_vehicle_not_belonging_to_customer_rejected(self, auth_client_manager, invoice_api_setup):
        setup = invoice_api_setup
        url = reverse('sales-invoice-list')
        payload = {
            'customer': setup['customer1'].pk,
            'vehicle': setup['vehicle2'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 1}]
        }
        response = auth_client_manager.post(url, payload, format='json')
        assert response.status_code == 400
        assert "خودرو" in str(response.data) and "متعلق به این مشتری نیست" in str(response.data)

    def test_invalid_tire_id_returns_400_bad_request(self, auth_client_manager, invoice_api_setup):
        setup = invoice_api_setup
        url = reverse('sales-invoice-list')
        payload = {
            'customer': setup['customer1'].pk,
            'vehicle': setup['vehicle1'].pk,
            'tire_items': [{'tire': 99999, 'quantity': 1}]
        }
        response = auth_client_manager.post(url, payload, format='json')
        assert response.status_code == 400

    def test_negative_tire_quantity_returns_400_bad_request(self, auth_client_manager, invoice_api_setup):
        setup = invoice_api_setup
        url = reverse('sales-invoice-list')
        payload = {
            'customer': setup['customer1'].pk,
            'vehicle': setup['vehicle1'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': -3}]
        }
        response = auth_client_manager.post(url, payload, format='json')
        assert response.status_code == 400

    def test_negative_unit_price_returns_400_bad_request(self, auth_client_manager, invoice_api_setup):
        setup = invoice_api_setup
        url = reverse('sales-invoice-list')
        payload = {
            'customer': setup['customer1'].pk,
            'vehicle': setup['vehicle1'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 1, 'unit_price': -1000}]
        }
        response = auth_client_manager.post(url, payload, format='json')
        assert response.status_code == 400

    def test_invalid_service_id_returns_400_bad_request(self, auth_client_manager, invoice_api_setup):
        setup = invoice_api_setup
        url = reverse('sales-invoice-list')
        payload = {
            'customer': setup['customer1'].pk,
            'service_items': [{'service': 88888, 'quantity': 1}]
        }
        response = auth_client_manager.post(url, payload, format='json')
        assert response.status_code == 400

    def test_technician_blocked_from_creating_purchase_invoice(self, auth_client_technician, invoice_api_setup):
        setup = invoice_api_setup
        url = reverse('purchase-invoice-list')
        payload = {
            'supplier': setup['supplier'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 5}]
        }
        response = auth_client_technician.post(url, payload, format='json')
        assert response.status_code == 403

    def test_purchase_invoice_invalid_items_returns_400(self, auth_client_warehouse, invoice_api_setup):
        setup = invoice_api_setup
        url = reverse('purchase-invoice-list')

        res1 = auth_client_warehouse.post(url, {
            'supplier': setup['supplier'].pk,
            'tire_items': [{'tire': 99999, 'quantity': 5}]
        }, format='json')
        assert res1.status_code == 400

        res2 = auth_client_warehouse.post(url, {
            'supplier': setup['supplier'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 0}]
        }, format='json')
        assert res2.status_code == 400

        res3 = auth_client_warehouse.post(url, {
            'supplier': setup['supplier'].pk,
            'tire_items': []
        }, format='json')
        assert res3.status_code == 400

    def test_double_cancel_invoice_raises_validation_error(self, auth_client_manager, invoice_api_setup):
        setup = invoice_api_setup
        url_create = reverse('sales-invoice-list')
        res_create = auth_client_manager.post(url_create, {
            'customer': setup['customer1'].pk,
            'vehicle': setup['vehicle1'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 2}]
        }, format='json')
        invoice_id = res_create.data['sales_invoice_id']
        cancel_url = reverse('sales-invoice-cancel', kwargs={'pk': invoice_id})

        res_cancel1 = auth_client_manager.post(cancel_url)
        assert res_cancel1.status_code == 200

        res_cancel2 = auth_client_manager.post(cancel_url)
        assert res_cancel2.status_code == 400
        assert "قبلاً لغو شده است" in str(res_cancel2.data)

    def test_financial_vouchers_protect_cascade_on_invoice_delete(self, invoice_api_setup, manager_user):
        setup = invoice_api_setup
        sales_inv = SalesInvoice.objects.create(
            customer=setup['customer1'],
            total_amount=Decimal('1000000'),
            created_by=manager_user
        )
        ReceiptVoucher.objects.create(
            sales_invoice=sales_inv,
            amount=Decimal('500000')
        )
        with pytest.raises(ProtectedError):
            sales_inv.delete()

        purchase_inv = PurchaseInvoice.objects.create(
            supplier=setup['supplier'],
            total_amount=Decimal('2000000'),
            created_by=manager_user
        )
        PaymentVoucher.objects.create(
            purchase_invoice=purchase_inv,
            amount=Decimal('1000000')
        )
        with pytest.raises(ProtectedError):
            purchase_inv.delete()
