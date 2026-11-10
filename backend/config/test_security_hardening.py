import runpy
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.checks import Warning as CheckWarning
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, override_settings

from apps.accounts.models import User, UserRole
from config import checks

SETTINGS_PATH = str(Path(__file__).with_name('settings.py'))
LEGACY_COMMITTED_KEY = 'django-insecure-tire-shop-production-secret-key-shayan-nami-2026'


@pytest.fixture
def load_settings(monkeypatch):
    def load(**env):
        with monkeypatch.context() as ctx:
            for name in (
                'DJANGO_SECRET_KEY', 'DJANGO_DEBUG', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE',
                'DB_ENGINE', 'USE_SQL_SERVER',
            ):
                ctx.delenv(name, raising=False)
            for name, value in env.items():
                ctx.setenv(name, value)
            with patch('dotenv.load_dotenv', return_value=False), warnings.catch_warnings():
                warnings.simplefilter('ignore')
                return runpy.run_path(SETTINGS_PATH)
    return load


class TestSecretKey:

    def test_no_committed_fallback_constant(self, load_settings):
        namespace = load_settings(DJANGO_DEBUG='True')
        assert 'INSECURE_DEFAULT_SECRET' not in namespace
        assert LEGACY_COMMITTED_KEY not in Path(SETTINGS_PATH).read_text(encoding='utf-8')

    def test_debug_without_key_generates_random_per_process_key_and_warns(self, monkeypatch):
        monkeypatch.delenv('DJANGO_SECRET_KEY', raising=False)
        monkeypatch.setenv('DJANGO_DEBUG', 'True')
        keys = []
        for _ in range(2):
            with patch('dotenv.load_dotenv', return_value=False), pytest.warns(RuntimeWarning, match='DJANGO_SECRET_KEY'):
                keys.append(runpy.run_path(SETTINGS_PATH)['SECRET_KEY'])
        assert all(len(key) >= 50 for key in keys)
        assert keys[0] != keys[1]

    def test_production_without_key_fails_hard(self, load_settings):
        with pytest.raises(ImproperlyConfigured, match='DJANGO_SECRET_KEY'):
            load_settings(DJANGO_DEBUG='False')

    @pytest.mark.parametrize('key', [LEGACY_COMMITTED_KEY, 'django-insecure-anything-else'])
    def test_production_rejects_django_insecure_keys(self, load_settings, key):
        with pytest.raises(ImproperlyConfigured, match='django-insecure-'):
            load_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY=key)

    def test_explicit_key_is_used_unchanged(self, load_settings):
        namespace = load_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY='explicit-production-key-0123456789')
        assert namespace['SECRET_KEY'] == 'explicit-production-key-0123456789'


class TestSecureCookieDefaults:

    @pytest.mark.parametrize('debug, expected', [('False', True), ('True', False)])
    def test_defaults_follow_debug(self, load_settings, debug, expected):
        namespace = load_settings(DJANGO_DEBUG=debug, DJANGO_SECRET_KEY='cookie-defaults-test-key-0123456789')
        assert namespace['SESSION_COOKIE_SECURE'] is expected
        assert namespace['CSRF_COOKIE_SECURE'] is expected

    @pytest.mark.parametrize('value, expected', [('False', False), ('0', False), ('True', True), ('', True)])
    def test_explicit_env_wins_and_blank_means_default(self, load_settings, value, expected):
        namespace = load_settings(
            DJANGO_DEBUG='False', DJANGO_SECRET_KEY='cookie-defaults-test-key-0123456789',
            SESSION_COOKIE_SECURE=value, CSRF_COOKIE_SECURE=value,
        )
        assert namespace['SESSION_COOKIE_SECURE'] is expected
        assert namespace['CSRF_COOKIE_SECURE'] is expected

    def test_hsts_and_ssl_redirect_stay_opt_in(self, load_settings):
        namespace = load_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY='cookie-defaults-test-key-0123456789')
        assert namespace['SECURE_SSL_REDIRECT'] is False
        assert namespace['SECURE_HSTS_SECONDS'] == 0


class TestDeploymentChecks:
    PROXY_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    def test_proxy_header_without_num_proxies_warns(self):
        with override_settings(DEBUG=False, SECURE_PROXY_SSL_HEADER=self.PROXY_HEADER, REST_FRAMEWORK={'NUM_PROXIES': 0}):
            result = checks.check_proxy_throttle_identity(None)
        assert [w.id for w in result] == ['tireshop.W001']
        assert isinstance(result[0], CheckWarning)

    def test_proxy_check_is_quiet_when_configured_or_irrelevant(self):
        with override_settings(DEBUG=False, SECURE_PROXY_SSL_HEADER=self.PROXY_HEADER, REST_FRAMEWORK={'NUM_PROXIES': 1}):
            assert checks.check_proxy_throttle_identity(None) == []
        with override_settings(DEBUG=False, SECURE_PROXY_SSL_HEADER=None, REST_FRAMEWORK={'NUM_PROXIES': 0}):
            assert checks.check_proxy_throttle_identity(None) == []
        with override_settings(DEBUG=True, SECURE_PROXY_SSL_HEADER=self.PROXY_HEADER, REST_FRAMEWORK={'NUM_PROXIES': 0}):
            assert checks.check_proxy_throttle_identity(None) == []

    def test_locmem_cache_warns_outside_debug(self):
        locmem = {'default': {'BACKEND': checks.LOCMEM_BACKEND}}
        with override_settings(DEBUG=False, CACHES=locmem):
            assert [w.id for w in checks.check_throttle_cache_is_shared(None)] == ['tireshop.W002']
        with override_settings(DEBUG=True, CACHES=locmem):
            assert checks.check_throttle_cache_is_shared(None) == []

    def test_shared_cache_does_not_warn(self):
        redis = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': 'redis://x/0'}}
        with override_settings(DEBUG=False, CACHES=redis):
            assert checks.check_throttle_cache_is_shared(None) == []

    def test_checks_are_registered_as_deploy_checks(self):
        from django.core.checks.registry import registry

        deploy_checks = registry.get_checks(include_deployment_checks=True)
        default_checks = registry.get_checks(include_deployment_checks=False)
        for check in (checks.check_proxy_throttle_identity, checks.check_throttle_cache_is_shared):
            assert check in deploy_checks
            assert check not in default_checks


@pytest.mark.django_db
class TestAdminLoginThrottle:
    LOGIN_URL = '/admin/login/'

    def _post(self, client, username, ip='10.0.0.1'):
        return client.post(
            self.LOGIN_URL, {'username': username, 'password': 'wrong-password', 'next': '/admin/'}, REMOTE_ADDR=ip,
        )

    def test_get_is_never_throttled(self):
        client = Client()
        for _ in range(10):
            assert client.get(self.LOGIN_URL).status_code == 200

    def test_per_ip_limit_blocks_with_429_and_retry_after(self):
        client = Client()
        for i in range(5):
            assert self._post(client, f'user_{i}').status_code == 200
        blocked = self._post(client, 'user_99')
        assert blocked.status_code == 429
        assert int(blocked['Retry-After']) > 0
        assert 'بیش از حد مجاز است' in blocked.content.decode()

    def test_other_ip_is_not_affected_by_blocked_ip(self):
        client = Client()
        for i in range(6):
            self._post(client, f'user_{i}')
        assert self._post(client, 'someone_else', ip='10.0.0.2').status_code == 200

    def test_per_username_limit_applies_across_ips(self):
        client = Client()
        for i in range(5):
            assert self._post(client, 'Victim', ip=f'10.1.0.{i}').status_code == 200
        assert self._post(client, ' victim ', ip='10.1.0.200').status_code == 429

    def test_throttle_does_not_leak_into_api_login_bucket(self):
        client = Client()
        for i in range(6):
            self._post(client, f'user_{i}')
        response = client.post(
            '/api/v1/auth/login/', {'username': 'nobody', 'password': 'x'}, REMOTE_ADDR='10.0.0.1',
        )
        assert response.status_code in (400, 401)

    def test_valid_login_still_works_within_the_limit(self):
        User.objects.create_superuser(username='admin_ok', password='S3cure-Passw0rd!', role=UserRole.MANAGER)
        client = Client()
        response = client.post(
            self.LOGIN_URL, {'username': 'admin_ok', 'password': 'S3cure-Passw0rd!', 'next': '/admin/'},
        )
        assert response.status_code == 302
        assert response['Location'] == '/admin/'
