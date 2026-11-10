import threading
from decimal import Decimal
import pytest
from django.urls import reverse
from django.db import IntegrityError, connection
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer
from apps.suppliers.models import Supplier
from apps.invoices.models import SalesInvoice, InvoiceStatus
from apps.invoices.services import (
    create_sales_invoice_service, confirm_sales_invoice_service,
    create_sales_return_service
)
from utils.exceptions import custom_exception_handler


@pytest.mark.django_db
class TestWorkshopServicesRBAC:

    def test_workshop_services_technician_blocked_from_mutations(self, auth_client_technician):
        url_list = reverse('service-list')
        res_get = auth_client_technician.get(url_list)
        assert res_get.status_code == status.HTTP_200_OK

        res_post = auth_client_technician.post(url_list, {
            'service_name': 'تعویض لنت غیرمجاز',
            'price': '150000.00'
        })
        assert res_post.status_code == status.HTTP_403_FORBIDDEN

    def test_workshop_services_manager_can_mutate(self, auth_client_manager, auth_client_technician):
        url_list = reverse('service-list')
        res_create = auth_client_manager.post(url_list, {
            'service_name': 'تنظیم باد با نیتروژن',
            'price': '80000.00',
            'description': 'سرویس باد نیتروژن'
        })
        assert res_create.status_code == status.HTTP_201_CREATED
        service_id = res_create.data['service_id']

        url_detail = reverse('service-detail', kwargs={'pk': service_id})
        res_del_tech = auth_client_technician.delete(url_detail)
        assert res_del_tech.status_code == status.HTTP_403_FORBIDDEN

        res_del_mgr = auth_client_manager.delete(url_detail)
        assert res_del_mgr.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestPasswordValidationOnUserCreation:

    def test_weak_password_rejected_on_user_creation(self, auth_client_manager):
        url = reverse('user-list')
        payload = {
            'username': 'weak_user_test',
            'password': '1',
            'full_name': 'کاربر با پسورد ضعیف',
            'role': 'TECHNICIAN'
        }
        response = auth_client_manager.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password' in str(response.data)

    def test_strong_password_accepted_on_user_creation(self, auth_client_manager):
        url = reverse('user-list')
        payload = {
            'username': 'strong_user_test',
            'password': 'SecureP@ssword1403!',
            'full_name': 'کاربر با پسورد قوی',
            'role': 'TECHNICIAN'
        }
        response = auth_client_manager.post(url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['username'] == 'strong_user_test'

    def test_weak_password_rejected_on_user_update(self, auth_client_manager, manager_user):
        url = reverse('user-detail', kwargs={'pk': manager_user.pk})
        response = auth_client_manager.patch(url, {'password': '123'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password' in str(response.data)


@pytest.mark.django_db
class TestDraftSalesInvoiceAndConfirmation:

    @pytest.fixture
    def setup_data(self, manager_user):
        brand = Brand.objects.create(brand_name='بارز پیش‌نویس')
        size = Size.objects.create(size_name='185/65R15')
        tire = Tire.objects.create(
            tire_name='بارز تست پیش‌نویس',
            brand=brand,
            size=size,
            stock_quantity=10,
            purchase_price=Decimal('1000000.00'),
            sale_price=Decimal('1500000.00')
        )
        StockMovement.objects.create(
            tire=tire,
            quantity=10,
            movement_type=StockMovementType.INITIAL_STOCK,
            balance_after=10,
            unit_cost=Decimal('1000000.00'),
            user=manager_user,
            description='موجودی اولیه'
        )
        customer = Customer.objects.create(full_name='مشتری تست پیش‌نویس', phone_number='09121112233')
        return {'tire': tire, 'customer': customer}

    def test_draft_invoice_does_not_deduct_stock_until_confirmed(
        self, auth_client_manager, setup_data, manager_user
    ):
        tire = setup_data['tire']
        customer = setup_data['customer']

        create_url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.DRAFT,
            'tire_items': [{'tire': tire.pk, 'quantity': 4, 'unit_price': '1500000.00'}]
        }
        res_create = auth_client_manager.post(create_url, payload, format='json')
        assert res_create.status_code == status.HTTP_201_CREATED
        invoice_id = res_create.data['sales_invoice_id']
        assert res_create.data['status'] == InvoiceStatus.DRAFT

        tire.refresh_from_db()
        assert tire.stock_quantity == 10
        assert not StockMovement.objects.filter(sales_invoice_id=invoice_id).exists()

        confirm_url = reverse('sales-invoice-confirm', kwargs={'pk': invoice_id})
        res_confirm = auth_client_manager.post(confirm_url)
        assert res_confirm.status_code == status.HTTP_200_OK

        tire.refresh_from_db()
        assert tire.stock_quantity == 6

        sale_movement = StockMovement.objects.filter(
            sales_invoice_id=invoice_id,
            movement_type=StockMovementType.SALE
        ).first()
        assert sale_movement is not None
        assert sale_movement.quantity == -4
        assert sale_movement.balance_after == 6

        inv = SalesInvoice.objects.get(pk=invoice_id)
        assert inv.status == InvoiceStatus.CONFIRMED

        res_confirm_again = auth_client_manager.post(confirm_url)
        assert res_confirm_again.status_code == status.HTTP_400_BAD_REQUEST
        assert "پیش" in str(res_confirm_again.data)

    def test_confirm_draft_fails_if_insufficient_stock(
        self, auth_client_manager, setup_data
    ):
        tire = setup_data['tire']
        customer = setup_data['customer']

        create_url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.DRAFT,
            'tire_items': [{'tire': tire.pk, 'quantity': 15, 'unit_price': '1500000.00'}]
        }
        res_create = auth_client_manager.post(create_url, payload, format='json')
        assert res_create.status_code == status.HTTP_201_CREATED
        invoice_id = res_create.data['sales_invoice_id']

        confirm_url = reverse('sales-invoice-confirm', kwargs={'pk': invoice_id})
        res_confirm = auth_client_manager.post(confirm_url)
        assert res_confirm.status_code == status.HTTP_400_BAD_REQUEST
        assert "کافی نیست" in str(res_confirm.data)

        tire.refresh_from_db()
        assert tire.stock_quantity == 10

    def test_sales_return_blocked_on_draft_sales_invoice(
        self, auth_client_manager, setup_data, manager_user
    ):
        tire = setup_data['tire']
        customer = setup_data['customer']

        create_url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.DRAFT,
            'tire_items': [{'tire': tire.pk, 'quantity': 2, 'unit_price': '1500000.00'}]
        }
        res_create = auth_client_manager.post(create_url, payload, format='json')
        assert res_create.status_code == status.HTTP_201_CREATED
        invoice_id = res_create.data['sales_invoice_id']

        inv = SalesInvoice.objects.get(pk=invoice_id)
        tire_item = inv.tire_items.first()

        from rest_framework.exceptions import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            create_sales_return_service(
                invoice=inv,
                items_data=[{'sales_invoice_tire_item_id': tire_item.pk, 'quantity': 1}],
                reason='مرجوعی فاکتور پیش‌نویس غیرمجاز',
                user=manager_user
            )
        assert "پیش" in str(exc_info.value) or "CONFIRMED" in str(exc_info.value)

    def test_confirm_endpoint_returns_rich_contract(
        self, auth_client_manager, setup_data
    ):
        tire = setup_data['tire']
        customer = setup_data['customer']

        create_url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.DRAFT,
            'tire_items': [{'tire': tire.pk, 'quantity': 2, 'unit_price': '1500000.00'}]
        }
        res_create = auth_client_manager.post(create_url, payload, format='json')
        invoice_id = res_create.data['sales_invoice_id']

        confirm_url = reverse('sales-invoice-confirm', kwargs={'pk': invoice_id})
        res_confirm = auth_client_manager.post(confirm_url)
        assert res_confirm.status_code == status.HTTP_200_OK

        assert 'invoice' in res_confirm.data
        assert res_confirm.data['invoice']['status'] == InvoiceStatus.CONFIRMED
        assert res_confirm.data['status'] == InvoiceStatus.CONFIRMED
        assert 'invoice_number' in res_confirm.data
        assert res_confirm.data['invoice_number'].startswith('S-')


@pytest.mark.django_db
class TestInvoiceFullSerializerContract:

    def test_sales_invoice_post_returns_invoice_number_and_rich_fields(
        self, auth_client_manager, manager_user
    ):
        brand = Brand.objects.create(brand_name='بارز قرارداد')
        size = Size.objects.create(size_name='185/65R14')
        tire = Tire.objects.create(
            tire_name='بارز تست قرارداد',
            brand=brand,
            size=size,
            stock_quantity=20,
            purchase_price=Decimal('1000000.00'),
            sale_price=Decimal('1500000.00')
        )
        customer = Customer.objects.create(full_name='مشتری قرارداد', phone_number='09129998877')

        url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'tire_items': [{'tire': tire.pk, 'quantity': 2, 'unit_price': '1500000.00'}]
        }
        response = auth_client_manager.post(url, payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert 'invoice_number' in response.data
        assert response.data['invoice_number'].startswith('S-')
        assert 'tire_items' in response.data
        assert len(response.data['tire_items']) == 1
        assert response.data['tire_items'][0]['tire_name'] == 'بارز تست قرارداد'

    def test_purchase_invoice_post_returns_invoice_number_and_rich_fields(
        self, auth_client_manager, manager_user
    ):
        brand = Brand.objects.create(brand_name='کویر قرارداد خرید')
        size = Size.objects.create(size_name='205/55R16')
        tire = Tire.objects.create(
            tire_name='کویر خرید تست',
            brand=brand,
            size=size,
            stock_quantity=0,
            purchase_price=Decimal('2000000.00'),
            sale_price=Decimal('2500000.00')
        )
        supplier = Supplier.objects.create(supplier_name='تأمین‌کننده تست قرارداد')

        url = reverse('purchase-invoice-list')
        payload = {
            'supplier': supplier.pk,
            'tire_items': [{'tire': tire.pk, 'quantity': 5, 'unit_cost': '2000000.00'}]
        }
        response = auth_client_manager.post(url, payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert 'invoice_number' in response.data
        assert response.data['invoice_number'].startswith('P-')
        assert 'tire_items' in response.data
        assert len(response.data['tire_items']) == 1


@pytest.mark.django_db
class TestReportsRobustnessAndProfitability:

    def test_sales_by_date_invalid_date_returns_400(self, auth_client_manager):
        url = reverse('sales-by-date-report')
        res_bad_start = auth_client_manager.get(f"{url}?start_date=invalid-date-string")
        assert res_bad_start.status_code == status.HTTP_400_BAD_REQUEST

        res_bad_end = auth_client_manager.get(f"{url}?end_date=9999-99-99")
        assert res_bad_end.status_code == status.HTTP_400_BAD_REQUEST

        res_valid = auth_client_manager.get(f"{url}?start_date=1403/01/01&end_date=1403/12/29")
        assert res_valid.status_code == status.HTTP_200_OK

    def test_profitability_report_accounts_for_invoice_discount(
        self, auth_client_manager, manager_user
    ):
        brand = Brand.objects.create(brand_name='یزد سودآوری تخفیف')
        size = Size.objects.create(size_name='185/65R15')
        tire = Tire.objects.create(
            tire_name='یزد تست تخفیف سود',
            brand=brand,
            size=size,
            stock_quantity=10,
            purchase_price=Decimal('1000000.00'),
            sale_price=Decimal('2000000.00')
        )
        customer = Customer.objects.create(full_name='مشتری سود تخفیف', phone_number='09128887766')

        create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('2000000.00')}],
            service_items_data=[],
            discount_percent=Decimal('20.00'),
            created_by=manager_user
        )

        url = reverse('profitability-report')
        response = auth_client_manager.get(url)
        assert response.status_code == status.HTTP_200_OK

        item = next((x for x in response.data if x['tire_id'] == tire.pk), None)
        assert item is not None
        assert item['total_sold'] == 1
        assert item['total_revenue'] == 1600000.0
        assert item['total_cost'] == 1000000.0
        assert item['total_profit'] == 600000.0

    def test_sales_by_brand_invalid_id_returns_400(self, auth_client_manager):
        url = reverse('sales-by-brand-report')
        res_bad_brand = auth_client_manager.get(f"{url}?brand_id=invalid_text")
        assert res_bad_brand.status_code == status.HTTP_400_BAD_REQUEST
        assert 'brand_id' in str(res_bad_brand.data)

    def test_sales_by_brand_valid_id_returns_200(self, auth_client_manager):
        url = reverse('sales-by-brand-report')
        res_valid = auth_client_manager.get(f"{url}?brand_id=1")
        assert res_valid.status_code == status.HTTP_200_OK


class TestCustomExceptionHandler:

    def test_django_validation_error_converted_to_400(self):
        exc = DjangoValidationError("خطای اعتبارسنجی مدل")
        response = custom_exception_handler(exc, {})
        assert response is not None
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False

    def test_integrity_error_converted_to_clean_400(self):
        exc = IntegrityError("duplicate key value violates unique constraint")
        response = custom_exception_handler(exc, {})
        assert response is not None
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert 'یکپارچگی' in str(response.data['errors'])


@pytest.mark.skipif(
    connection.vendor == 'sqlite',
    reason="تست همروندی چندنخی و قفل ردیف نیازمند پایگاه داده رابطه‌ای چندنخی (PostgreSQL) است."
)
@pytest.mark.django_db(transaction=True)
class TestConcurrentDraftConfirmation:

    def test_concurrent_draft_confirmations_prevent_overselling(self, manager_user):
        brand = Brand.objects.create(brand_name='بارز همروندی پیش‌نویس')
        size = Size.objects.create(size_name='195/65R15')
        tire = Tire.objects.create(
            tire_name='بارز تایید همروند',
            brand=brand,
            size=size,
            stock_quantity=4,
            purchase_price=Decimal('1000000.00'),
            sale_price=Decimal('1500000.00')
        )
        StockMovement.objects.create(
            tire=tire,
            quantity=4,
            movement_type=StockMovementType.INITIAL_STOCK,
            balance_after=4,
            unit_cost=Decimal('1000000.00'),
            user=manager_user,
            description='موجودی اولیه'
        )
        customer = Customer.objects.create(full_name='مشتری همروندی پیش‌نویس', phone_number='09127771122')

        inv1 = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 3, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            status=InvoiceStatus.DRAFT,
            created_by=manager_user
        )
        inv2 = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 3, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            status=InvoiceStatus.DRAFT,
            created_by=manager_user
        )

        num_threads = 2
        barrier = threading.Barrier(num_threads, timeout=10)
        successes = []
        errors = []

        def worker(inv_id):
            try:
                barrier.wait()
                confirmed = confirm_sales_invoice_service(inv_id, user=manager_user)
                successes.append(confirmed.pk)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        t1 = threading.Thread(target=worker, args=(inv1.pk,))
        t2 = threading.Thread(target=worker, args=(inv2.pk,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert not t1.is_alive()
        assert not t2.is_alive()

        assert len(successes) == 1
        assert len(errors) == 1
        assert "کافی نیست" in str(errors[0])

        tire.refresh_from_db()
        assert tire.stock_quantity == 1
