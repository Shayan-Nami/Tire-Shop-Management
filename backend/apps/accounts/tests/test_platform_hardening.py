from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.urls import reverse

from apps.accounts.models import UserRole

User = get_user_model()


@pytest.mark.django_db
def test_profile_update_normalizes_persian_phone_and_rejects_invalid(auth_client_technician, technician_user):
    url = reverse('user_profile')

    res = auth_client_technician.patch(
        url,
        {'full_name': 'تکنسین نمونه', 'phone_number': '۰۹۱۲۳۴۵۶۷۸۹'},
        format='json',
    )
    assert res.status_code == 200
    assert res.data['phone_number'] == '09123456789'
    technician_user.refresh_from_db()
    assert technician_user.phone_number == '09123456789'

    res_blank = auth_client_technician.patch(url, {'phone_number': '   '}, format='json')
    assert res_blank.status_code == 200
    technician_user.refresh_from_db()
    assert technician_user.phone_number is None

    res_invalid = auth_client_technician.patch(url, {'phone_number': '12345'}, format='json')
    assert res_invalid.status_code == 400
    assert 'phone_number' in str(res_invalid.data)


@pytest.mark.django_db
def test_user_create_sets_password_before_initial_save_and_is_atomic(auth_client_manager):
    seen_passwords_on_create = []

    def check_hashed_on_insert(sender, instance, **kwargs):
        if instance.pk is None and instance.username == 'hashed_first_user':
            seen_passwords_on_create.append(instance.password)

    pre_save.connect(check_hashed_on_insert, sender=User)
    try:
        res = auth_client_manager.post(
            reverse('user-list'),
            {
                'username': 'hashed_first_user',
                'password': 'StrongPassword123!',
                'full_name': 'کاربر تستی',
                'role': UserRole.WAREHOUSE,
                'phone_number': '۰۹۱۳۱۱۱۲۲۳۳',
            },
            format='json',
        )
    finally:
        pre_save.disconnect(check_hashed_on_insert, sender=User)

    assert res.status_code == 201
    assert len(seen_passwords_on_create) == 1
    assert seen_passwords_on_create[0].startswith('pbkdf2_')
    assert res.data['phone_number'] == '09131112233'

    with patch.object(User, 'save', side_effect=RuntimeError('save failed')):
        res_fail = auth_client_manager.post(
            reverse('user-list'),
            {
                'username': 'atomic_fail_user',
                'password': 'StrongPassword123!',
                'role': UserRole.TECHNICIAN,
            },
            format='json',
        )
        assert res_fail.status_code == 500
    assert not User.objects.filter(username='atomic_fail_user').exists()
