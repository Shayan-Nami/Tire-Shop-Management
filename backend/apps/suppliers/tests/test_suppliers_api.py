import pytest
from django.urls import reverse
from apps.suppliers.models import Supplier


@pytest.mark.django_db
class TestSuppliersAPI:

    def test_unauthenticated_cannot_access_suppliers(self, api_client):
        url = reverse('supplier-list')
        res = api_client.get(url)
        assert res.status_code == 401

    def test_technician_can_list_suppliers_read_only(self, auth_client_technician):
        Supplier.objects.create(supplier_name='شرکت لاستیک بارز تهران', phone_number='02188888888')
        url = reverse('supplier-list')
        res = auth_client_technician.get(url)
        assert res.status_code == 200
        assert len(res.data['results']) >= 1

    def test_technician_cannot_create_supplier(self, auth_client_technician):
        url = reverse('supplier-list')
        payload = {'supplier_name': 'تأمین‌کننده کویر', 'phone_number': '02177777777'}
        res = auth_client_technician.post(url, payload, format='json')
        assert res.status_code == 403

    def test_warehouse_can_create_and_update_supplier(self, auth_client_warehouse):
        url = reverse('supplier-list')
        payload = {'supplier_name': 'شرکت بازرگانی دنا', 'phone_number': '02166666666', 'address': 'تهران، خیابان چراغ برق'}
        res = auth_client_warehouse.post(url, payload, format='json')
        assert res.status_code == 201
        supplier_id = res.data['supplier_id']

        detail_url = reverse('supplier-detail', kwargs={'pk': supplier_id})
        update_res = auth_client_warehouse.patch(detail_url, {'phone_number': '02166667777'}, format='json')
        assert update_res.status_code == 200
        assert update_res.data['phone_number'] == '02166667777'

    def test_manager_can_delete_supplier(self, auth_client_manager):
        sup = Supplier.objects.create(supplier_name='تأمین‌کننده موقت', phone_number='02111111111')
        detail_url = reverse('supplier-detail', kwargs={'pk': sup.pk})
        res = auth_client_manager.delete(detail_url)
        assert res.status_code == 204
        assert not Supplier.objects.filter(pk=sup.pk).exists()

    def test_duplicate_supplier_name_returns_400(self, auth_client_warehouse):
        Supplier.objects.create(supplier_name='یزد تایر مرکزی')
        url = reverse('supplier-list')
        res = auth_client_warehouse.post(url, {'supplier_name': 'یزد تایر مرکزی'}, format='json')
        assert res.status_code == 400

    def test_supplier_search(self, auth_client_warehouse):
        Supplier.objects.create(supplier_name='شرکت لاستیک پارس', phone_number='02122222222')
        Supplier.objects.create(supplier_name='صنایع لاستیک گلدستون', phone_number='02133333333')

        url = f"{reverse('supplier-list')}?search=گلدستون"
        res = auth_client_warehouse.get(url)
        assert res.status_code == 200
        assert len(res.data['results']) == 1
        assert res.data['results'][0]['supplier_name'] == 'صنایع لاستیک گلدستون'
