import pytest
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.customers.models import Customer
from apps.accounts.models import UserRole

User = get_user_model()


@pytest.fixture
def auth_client_manager(db):
    manager = User.objects.create_user(
        username='manager_cust_test',
        password='Password123!',
        role=UserRole.MANAGER,
        full_name='مدیر سیستم و مشتریان',
        is_staff=True,
        is_superuser=True
    )
    client = APIClient()
    client.force_authenticate(user=manager)
    return client


@pytest.mark.django_db
class TestCustomerUniqueAndSanitization:

    def test_customer_duplicate_phone_number_returns_400_persian_error(self, auth_client_manager):
        Customer.objects.create(full_name='مشتری اول', phone_number='09121112233')

        url = reverse('customer-list')
        payload = {
            'full_name': 'مشتری دوم با همان شماره',
            'phone_number': '09121112233'
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert any(msg in str(res.data) for msg in ['از قبل موجود است', 'قبلاً برای مشتری دیگری ثبت شده است'])

    def test_customer_duplicate_national_code_returns_400_persian_error(self, auth_client_manager):
        Customer.objects.create(full_name='مشتری الف', phone_number='09121110001', national_code='0011223344')

        url = reverse('customer-list')
        payload = {
            'full_name': 'مشتری ب با همان کد ملی',
            'phone_number': '09121110002',
            'national_code': '0011223344'
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert any(msg in str(res.data) for msg in ['از قبل موجود است', 'قبلاً برای مشتری دیگری ثبت شده است'])

    def test_customer_multiple_null_or_empty_phone_and_national_code_allowed(self, auth_client_manager):
        url = reverse('customer-list')

        res1 = auth_client_manager.post(url, {'full_name': 'مشتری ناشناس ۱', 'phone_number': None, 'national_code': None}, format='json')
        assert res1.status_code == 201

        res2 = auth_client_manager.post(url, {'full_name': 'مشتری ناشناس ۲', 'phone_number': '', 'national_code': ''}, format='json')
        assert res2.status_code == 201

        res3 = auth_client_manager.post(url, {'full_name': 'مشتری ناشناس ۳', 'phone_number': '   ', 'national_code': None}, format='json')
        assert res3.status_code == 201

        c1 = Customer.objects.get(pk=res1.data['customer_id'])
        c2 = Customer.objects.get(pk=res2.data['customer_id'])
        c3 = Customer.objects.get(pk=res3.data['customer_id'])

        assert c1.phone_number is None and c1.national_code is None
        assert c2.phone_number is None and c2.national_code is None
        assert c3.phone_number is None and c3.national_code is None

    def test_user_duplicate_phone_number_returns_400_persian_error(self, auth_client_manager):
        User.objects.create_user(username='user_existing', password='Password123!', phone_number='09129998877')

        url = reverse('user-list')
        payload = {
            'username': 'user_new_duplicate_phone',
            'password': 'Password123!',
            'full_name': 'کاربر جدید',
            'phone_number': '09129998877',
            'role': UserRole.TECHNICIAN
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert any(msg in str(res.data) for msg in ['از قبل موجود است', 'قبلاً برای کاربر دیگری ثبت شده است'])

    def test_user_multiple_null_or_empty_phone_allowed(self, auth_client_manager):
        url = reverse('user-list')

        res1 = auth_client_manager.post(url, {
            'username': 'tech_no_phone_1',
            'password': 'Password123!',
            'role': UserRole.TECHNICIAN,
            'phone_number': ''
        }, format='json')
        assert res1.status_code == 201

        res2 = auth_client_manager.post(url, {
            'username': 'tech_no_phone_2',
            'password': 'Password123!',
            'role': UserRole.TECHNICIAN,
            'phone_number': None
        }, format='json')
        assert res2.status_code == 201

        u1 = User.objects.get(username='tech_no_phone_1')
        u2 = User.objects.get(username='tech_no_phone_2')
        assert u1.phone_number is None
        assert u2.phone_number is None

    def test_model_full_clean_raises_validation_error_on_duplicate(self):
        Customer.objects.create(full_name='مشتری الف', phone_number='09123334455')
        dup_customer = Customer(full_name='مشتری ب', phone_number='09123334455')

        with pytest.raises(ValidationError) as exc:
            dup_customer.full_clean()
        assert 'این شماره تماس قبلاً برای مشتری دیگری ثبت شده است' in str(exc.value)

    def test_vehicle_duplicate_license_plate_returns_field_validation_error(self, auth_client_manager):
        customer = Customer.objects.create(full_name='مشتری پلاک تکراری', phone_number='09124445566')
        url = reverse('vehicle-list')

        res_create = auth_client_manager.post(url, {
            'customer': customer.pk,
            'license_plate': '۱۲ب۳۴۵-ایران۱۱',
            'model': 'پژو ۲۰۷',
        }, format='json')
        assert res_create.status_code == 201
        assert res_create.data['license_plate'] == '12ب345-ایران11'

        res_dup = auth_client_manager.post(url, {
            'customer': customer.pk,
            'license_plate': '12ب345-ایران11',
            'model': 'سمند',
        }, format='json')
        assert res_dup.status_code == 400
        assert 'license_plate' in res_dup.data['errors']
        assert 'قبلاً ثبت شده است' in str(res_dup.data['errors']['license_plate'])

        res_self_patch = auth_client_manager.patch(
            reverse('vehicle-detail', kwargs={'pk': res_create.data['vehicle_id']}),
            {'license_plate': '12ب345-ایران11', 'model': 'پژو ۲۰۷ اتوماتیک'},
            format='json',
        )
        assert res_self_patch.status_code == 200
        assert res_self_patch.data['model'] == 'پژو ۲۰۷ اتوماتیک'
