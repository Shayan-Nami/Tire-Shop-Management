import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestRBACPermissionsAndAuth:

    def test_jwt_login_successful_and_returns_role(self, api_client, manager_user):
        url = reverse('token_obtain_pair')
        response = api_client.post(url, {
            'username': 'test_manager',
            'password': 'pass123'
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
