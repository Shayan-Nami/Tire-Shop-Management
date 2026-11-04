import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User, UserRole

from django.core.cache import cache

@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def manager_user(db):
    user, _ = User.objects.get_or_create(
        username='test_manager',
        defaults={
            'role': UserRole.MANAGER,
            'full_name': 'تست مدیر',
            'is_staff': False,
            'is_superuser': False
        }
    )
    user.set_password('pass123')
    user.save()
    return user

@pytest.fixture
def technician_user(db):
    user, _ = User.objects.get_or_create(
        username='test_tech',
        defaults={
            'role': UserRole.TECHNICIAN,
            'full_name': 'تست تکنسین'
        }
    )
    user.set_password('pass123')
    user.save()
    return user

@pytest.fixture
def warehouse_user(db):
    user, _ = User.objects.get_or_create(
        username='test_warehouse',
        defaults={
            'role': UserRole.WAREHOUSE,
            'full_name': 'تست انباردار'
        }
    )
    user.set_password('pass123')
    user.save()
    return user

@pytest.fixture
def auth_client_manager(manager_user):
    client = APIClient()
    client.force_authenticate(user=manager_user)
    return client

@pytest.fixture
def auth_client_technician(technician_user):
    client = APIClient()
    client.force_authenticate(user=technician_user)
    return client

@pytest.fixture
def auth_client_warehouse(warehouse_user):
    client = APIClient()
    client.force_authenticate(user=warehouse_user)
    return client


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(username='test_superuser', password='pass123', role=UserRole.MANAGER)
