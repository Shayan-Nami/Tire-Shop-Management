import pytest
from decimal import Decimal
from django.urls import reverse
from django.core.management import call_command
from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer, Vehicle
from apps.suppliers.models import Supplier
from apps.invoices.models import SalesInvoice, InvoiceStatus, PaymentStatus
from apps.invoices.services import (
    create_sales_invoice_service,
    cancel_sales_invoice_service,
    create_purchase_invoice_service
)
from rest_framework import status
from rest_framework.exceptions import ValidationError

@pytest.fixture
def catalog_setup(db):
    brand = Brand.objects.create(brand_name='تست بارز')
    size = Size.objects.create(size_name='185/65R14')
    tire = Tire.objects.create(
        tire_name='تایر تست',
        brand=brand,
        size=size,
        stock_quantity=10,
        purchase_price=Decimal('1000000'),
        sale_price=Decimal('1500000'),
        min_stock_alert=3
    )
    customer = Customer.objects.create(
        full_name='مشتری تست',
        phone_number='09100000000'
    )
    vehicle = Vehicle.objects.create(
        customer=customer,
        license_plate='11ت111-ایران11',
        model='پراید 111'
    )
    supplier = Supplier.objects.create(
        supplier_name='تأمین‌کننده تست'
    )
    return {
        'tire': tire,
        'customer': customer,
        'vehicle': vehicle,
        'supplier': supplier
    }

@pytest.mark.django_db
class TestInvoiceAndStockTransactions:

    def test_create_sales_invoice_deducts_stock(self, catalog_setup, manager_user):
        tire = catalog_setup['tire']
        customer = catalog_setup['customer']
        vehicle = catalog_setup['vehicle']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 3, 'unit_price': tire.sale_price}],
            service_items_data=[],
            discount_amount=Decimal('100000'),
            created_by=manager_user
        )

        assert invoice.sales_invoice_id is not None
        assert invoice.status == InvoiceStatus.CONFIRMED

        assert invoice.total_amount == Decimal('4400000.00')

        tire.refresh_from_db()
        assert tire.stock_quantity == 7

    def test_insufficient_stock_raises_error_and_rolls_back(self, catalog_setup, manager_user):
        tire = catalog_setup['tire']
        customer = catalog_setup['customer']

        with pytest.raises(ValidationError) as exc_info:
            create_sales_invoice_service(
                customer=customer,
                vehicle=None,
                tire_items_data=[{'tire': tire, 'quantity': 12, 'unit_price': tire.sale_price}],
                service_items_data=[],
                created_by=manager_user
            )

        assert "موجودی تایر" in str(exc_info.value)

        tire.refresh_from_db()
        assert tire.stock_quantity == 10
        assert SalesInvoice.objects.filter(customer=customer).count() == 0

    def test_cancel_sales_invoice_restores_stock(self, catalog_setup, manager_user):
        tire = catalog_setup['tire']
        customer = catalog_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': tire.sale_price}],
            service_items_data=[],
            created_by=manager_user
        )
        tire.refresh_from_db()
        assert tire.stock_quantity == 6

        cancel_sales_invoice_service(invoice)

        invoice.refresh_from_db()
        tire.refresh_from_db()
        assert invoice.status == InvoiceStatus.CANCELLED
        assert tire.stock_quantity == 10

    def test_purchase_invoice_increases_stock(self, catalog_setup, warehouse_user):
        tire = catalog_setup['tire']
        supplier = catalog_setup['supplier']

        initial_stock = tire.stock_quantity

        purchase_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 20, 'unit_cost': Decimal('1100000')}],
            created_by=warehouse_user
        )

        assert purchase_inv.purchase_invoice_id is not None
        assert purchase_inv.total_amount == Decimal('22000000.00')

        tire.refresh_from_db()
        assert tire.stock_quantity == initial_stock + 20
        assert tire.purchase_price == Decimal('1100000.00')

    def test_paid_sales_invoice_auto_creates_receipt_voucher_and_zeros_dashboard_receivables(
        self, catalog_setup, auth_client_manager, manager_user
    ):
        tire = catalog_setup['tire']
        customer = catalog_setup['customer']
        vehicle = catalog_setup['vehicle']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}],
            service_items_data=[],
            payment_status=PaymentStatus.PAID,
            payment_method='دستگاه کارتخوان',
            reference_number='POS-TEST-12345',
            created_by=manager_user
        )

        assert invoice.sales_invoice_id is not None
        assert invoice.payment_status == PaymentStatus.PAID
        assert invoice.total_amount == Decimal('3000000.00')

        receipts = invoice.receipts.filter(is_cancelled=False)
        assert receipts.exists()
        receipt = receipts.first()
        assert receipt.amount == invoice.total_amount
        assert receipt.reference_number == 'POS-TEST-12345'
        assert receipt.payment_method == 'دستگاه کارتخوان'

        dashboard_url = reverse('dashboard-stats')
        res_dash = auth_client_manager.get(dashboard_url)
        assert res_dash.status_code == status.HTTP_200_OK
        assert Decimal(str(res_dash.data['total_receivables'])) == Decimal('0.00')
        assert res_dash.data['unpaid_invoices_count'] == 0

        call_command('reconcile_payments')

