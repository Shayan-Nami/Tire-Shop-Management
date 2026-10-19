import pytest
from decimal import Decimal
from django.urls import reverse
from apps.services_app.models import Service


@pytest.mark.django_db
class TestServicesAPI:

    def test_unauthenticated_cannot_access_services(self, api_client):
        url = reverse('service-list')
        res = api_client.get(url)
        assert res.status_code == 401

    def test_technician_can_list_services_read_only(self, auth_client_technician):
        Service.objects.create(service_name='تعویض والف', price=Decimal('50000.00'))
        url = reverse('service-list')
        res = auth_client_technician.get(url)
        assert res.status_code == 200
        assert len(res.data['results']) >= 1

    def test_technician_cannot_create_service(self, auth_client_technician):
        url = reverse('service-list')
        payload = {'service_name': 'بالانس استاتیک', 'price': '120000.00'}
        res = auth_client_technician.post(url, payload, format='json')
        assert res.status_code == 403

    def test_manager_can_create_update_delete_service(self, auth_client_manager):
        url = reverse('service-list')
        # Create
        payload = {'service_name': 'تنظیم باد دیجیتال', 'price': '30000.00', 'description': 'با نیتروژن'}
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 201
        service_id = res.data['service_id']

        # Update
        detail_url = reverse('service-detail', kwargs={'pk': service_id})
        update_res = auth_client_manager.patch(detail_url, {'price': '40000.00'}, format='json')
        assert update_res.status_code == 200
        assert Decimal(str(update_res.data['price'])) == Decimal('40000.00')

        # Delete
        delete_res = auth_client_manager.delete(detail_url)
        assert delete_res.status_code == 204
        assert not Service.objects.filter(pk=service_id).exists()

    def test_negative_service_price_validation(self, auth_client_manager):
        url = reverse('service-list')
        payload = {'service_name': 'خدمت نامعتبر', 'price': '-1000.00'}
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400

    def test_service_search_filter(self, auth_client_technician):
        Service.objects.create(service_name='آپارات گرم لاستیک', price=Decimal('250000.00'))
        Service.objects.create(service_name='تنظیم زاویه چرخ', price=Decimal('350000.00'))

        url = f"{reverse('service-list')}?search=آپارات"
        res = auth_client_technician.get(url)
        assert res.status_code == 200
        assert len(res.data['results']) == 1
        assert res.data['results'][0]['service_name'] == 'آپارات گرم لاستیک'
