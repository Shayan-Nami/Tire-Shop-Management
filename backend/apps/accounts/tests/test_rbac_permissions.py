from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from apps.accounts.permissions import IsDocManagerOrDebug
from apps.catalog.models import Brand
from apps.suppliers.models import Supplier


@pytest.mark.django_db
class TestRBACPermissionsAndAuth:

    def test_jwt_login_successful_and_returns_role(self, api_client, manager_user):
        url = reverse('token_obtain_pair')
        response = api_client.post(url, {
            'username': 'test_manager',
            'password': 'pass123',
        })
        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert response.data['user']['role'] == 'MANAGER'
        assert response.data['user']['username'] == 'test_manager'

    def test_user_management_restricted_to_manager(self, auth_client_manager, auth_client_technician, auth_client_warehouse):
        url = reverse('user-list')

        res_manager = auth_client_manager.get(url)
        assert res_manager.status_code == 200

        res_tech = auth_client_technician.get(url)
        assert res_tech.status_code == 403

        res_warehouse = auth_client_warehouse.get(url)
        assert res_warehouse.status_code == 403

    def test_technician_can_view_tires_but_purchase_price_is_hidden(self, auth_client_technician, auth_client_manager):
        url = reverse('tire-list')

        res_tech = auth_client_technician.get(url)
        assert res_tech.status_code == 200
        if len(res_tech.data['results']) > 0:
            first_tire = res_tech.data['results'][0]
            assert 'purchase_price' not in first_tire

        res_manager = auth_client_manager.get(url)
        assert res_manager.status_code == 200
        if len(res_manager.data['results']) > 0:
            first_tire = res_manager.data['results'][0]
            assert 'purchase_price' in first_tire

    def test_warehouse_can_create_and_update_but_cannot_delete_catalog_or_suppliers(
        self,
        auth_client_manager,
        auth_client_warehouse,
        auth_client_technician,
    ):
        brand_list = reverse('brand-list')
        assert auth_client_technician.post(brand_list, {'brand_name': 'TechBrand'}, format='json').status_code == 403

        res_brand = auth_client_warehouse.post(brand_list, {'brand_name': 'WarehouseBrand'}, format='json')
        assert res_brand.status_code == 201
        brand_detail = reverse('brand-detail', args=[res_brand.data['brand_id']])
        assert auth_client_warehouse.patch(brand_detail, {'brand_name': 'WarehouseBrand2'}, format='json').status_code == 200
        assert auth_client_warehouse.delete(brand_detail).status_code == 403
        assert Brand.objects.filter(pk=res_brand.data['brand_id']).exists()
        assert auth_client_manager.delete(brand_detail).status_code == 204

        supplier_list = reverse('supplier-list')
        res_sup = auth_client_warehouse.post(
            supplier_list,
            {'supplier_name': 'WarehouseSupplier', 'phone_number': '02155667788'},
            format='json',
        )
        assert res_sup.status_code == 201
        sup_detail = reverse('supplier-detail', args=[res_sup.data['supplier_id']])
        assert auth_client_warehouse.patch(sup_detail, {'phone_number': '02155667799'}, format='json').status_code == 200
        assert auth_client_warehouse.delete(sup_detail).status_code == 403
        assert Supplier.objects.filter(pk=res_sup.data['supplier_id']).exists()
        assert auth_client_manager.delete(sup_detail).status_code == 204

    def test_doc_permission_reads_settings_flag(self, settings, monkeypatch, manager_user, warehouse_user):
        perm = IsDocManagerOrDebug()
        anon_req = SimpleNamespace(user=AnonymousUser())
        wh_req = SimpleNamespace(user=warehouse_user)
        mgr_req = SimpleNamespace(user=manager_user)

        settings.DEBUG = False
        settings.ENABLE_DOCS_IN_PROD = False
        monkeypatch.setenv('ENABLE_DOCS_IN_PROD', 'True')
        assert perm.has_permission(anon_req, None) is False
        assert perm.has_permission(wh_req, None) is False
        assert perm.has_permission(mgr_req, None) is True

        settings.ENABLE_DOCS_IN_PROD = True
        assert perm.has_permission(anon_req, None) is True
