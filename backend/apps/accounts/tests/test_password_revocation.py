import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserRole


User = get_user_model()
NEW_PASSWORD = 'Fresh-Cedar!8274'


def login(user, password='pass123', status=200):
    response = APIClient().post(reverse('token_obtain_pair'), {
        'username': user.username, 'password': password,
    }, format='json')
    assert response.status_code == status
    return response.data


def bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    return client


def assert_rejected(tokens):
    assert bearer(tokens['access']).get(reverse('user_profile')).status_code == 401
    response = APIClient().post(reverse('token_refresh'), {
        'refresh': tokens['refresh'],
    }, format='json')
    assert response.status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize('reset_path', ['self', 'manager'])
@pytest.mark.parametrize('role', [UserRole.TECHNICIAN, UserRole.MANAGER])
def test_password_change_revokes_every_session(technician_user, manager_user, reset_path, role):
    user = technician_user
    user.role = role
    user.save(update_fields=['role'])
    first = login(user)
    second = login(user)
    rotated = APIClient().post(reverse('token_refresh'), {
        'refresh': second['refresh'],
    }, format='json')
    assert rotated.status_code == 200
    manager_tokens = login(manager_user)

    if reset_path == 'self':
        response = bearer(first['access']).post(reverse('change_password'), {
            'old_password': 'pass123', 'new_password': NEW_PASSWORD,
        }, format='json')
    else:
        manager_user.is_superuser = False
        manager_user.save(update_fields=['is_superuser'])
        response = bearer(manager_tokens['access']).patch(
            reverse('user-detail', args=[user.pk]),
            {'password': NEW_PASSWORD}, format='json',
        )
    assert response.status_code == 200

    for tokens in [first, second, rotated.data]:
        assert_rejected(tokens)
    outstanding = OutstandingToken.objects.filter(user=user)
    assert outstanding.count() >= 3
    assert BlacklistedToken.objects.filter(token__in=outstanding).count() == outstanding.count()
    user.refresh_from_db()
    assert user.role == role
    assert user.check_password(NEW_PASSWORD)
    login(user, status=401)
    fresh = login(user, NEW_PASSWORD)
    assert bearer(fresh['access']).get(reverse('user_profile')).status_code == 200
    assert APIClient().post(reverse('token_refresh'), {
        'refresh': fresh['refresh'],
    }, format='json').status_code == 200
    assert bearer(manager_tokens['access']).get(reverse('user_profile')).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('missing_claim', [False, True])
def test_refresh_checks_password_hash_even_without_outstanding_record(technician_user, missing_claim):
    refresh = RefreshToken.for_user(technician_user)
    if missing_claim:
        del refresh[api_settings.REVOKE_TOKEN_CLAIM]
    tokens = {'refresh': str(refresh), 'access': str(refresh.access_token)}
    OutstandingToken.objects.filter(user=technician_user).delete()
    if not missing_claim:
        technician_user.set_password(NEW_PASSWORD)
        technician_user.save(update_fields=['password'])
    assert_rejected(tokens)


@pytest.mark.django_db
def test_inactive_user_cannot_use_existing_tokens_or_session(technician_user):
    tokens = login(technician_user)
    session = APIClient()
    assert session.login(username=technician_user.username, password='pass123')
    technician_user.is_active = False
    technician_user.save(update_fields=['is_active'])
    assert_rejected(tokens)
    assert session.get(reverse('user_profile')).status_code == 401
    login(technician_user, status=401)


@pytest.mark.django_db
def test_password_change_invalidates_existing_django_session(technician_user):
    session = APIClient()
    assert session.login(username=technician_user.username, password='pass123')
    tokens = login(technician_user)
    response = bearer(tokens['access']).post(reverse('change_password'), {
        'old_password': 'pass123', 'new_password': NEW_PASSWORD,
    }, format='json')
    assert response.status_code == 200
    assert session.get(reverse('user_profile')).status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize('reset_path', ['self', 'manager'])
def test_invalid_password_does_not_revoke_tokens(technician_user, manager_user, reset_path):
    tokens = login(technician_user)
    if reset_path == 'self':
        response = bearer(tokens['access']).post(reverse('change_password'), {
            'old_password': 'pass123', 'new_password': '123',
        }, format='json')
    else:
        response = bearer(login(manager_user)['access']).patch(
            reverse('user-detail', args=[technician_user.pk]),
            {'password': '123'}, format='json',
        )
    assert response.status_code == 400
    assert bearer(tokens['access']).get(reverse('user_profile')).status_code == 200
    assert not BlacklistedToken.objects.filter(token__user=technician_user).exists()


@pytest.mark.django_db
def test_non_manager_cannot_reset_another_user(technician_user, manager_user):
    response = bearer(login(technician_user)['access']).patch(
        reverse('user-detail', args=[manager_user.pk]),
        {'password': NEW_PASSWORD}, format='json',
    )
    assert response.status_code == 403
    manager_user.refresh_from_db()
    assert manager_user.check_password('pass123')


@pytest.mark.django_db
def test_profile_update_does_not_revoke_tokens(technician_user, manager_user):
    tokens = login(technician_user)
    response = bearer(login(manager_user)['access']).patch(
        reverse('user-detail', args=[technician_user.pk]),
        {'full_name': 'Updated profile'}, format='json',
    )
    assert response.status_code == 200
    assert bearer(tokens['access']).get(reverse('user_profile')).status_code == 200
    assert not BlacklistedToken.objects.filter(token__user=technician_user).exists()
