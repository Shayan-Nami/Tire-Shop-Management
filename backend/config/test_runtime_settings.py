import logging
import runpy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured


def _load_settings(monkeypatch, overrides):
    defaults = {
        'PYTHON_DOTENV_DISABLED': '1',
        'DJANGO_DEBUG': 'False',
        'DJANGO_TESTING': 'False',
        'DJANGO_SECRET_KEY': 'runtime-settings-test-key-not-for-deployment-20261112',
        'ALLOWED_HOSTS': None,
        'CORS_ALLOWED_ORIGINS': None,
        'CSRF_TRUSTED_ORIGINS': None,
        'REDIS_CACHE_URL': None,
        'ENABLE_DOCS_IN_PROD': None,
        'SESSION_COOKIE_SECURE': None,
        'CSRF_COOKIE_SECURE': None,
        'SECURE_SSL_REDIRECT': None,
        'SECURE_HSTS_SECONDS': None,
        'SECURE_HSTS_INCLUDE_SUBDOMAINS': None,
        'SECURE_HSTS_PRELOAD': None,
        'JWT_ACCESS_MINUTES': None,
        'JWT_REFRESH_HOURS': None,
        'JWT_REFRESH_DAYS': None,
        'JWT_MAX_SESSION_HOURS': None,
        'JWT_ROTATE_REFRESH_TOKENS': None,
    }
    with monkeypatch.context() as env:
        for key, value in {**defaults, **overrides}.items():
            if value is None:
                env.delenv(key, raising=False)
            else:
                env.setenv(key, value)
        return runpy.run_path(str(Path(__file__).with_name('settings.py')))


def test_python_dotenv_disabled_skips_load_dotenv(monkeypatch):
    with patch('dotenv.load_dotenv') as load_dotenv:
        _load_settings(monkeypatch, {'PYTHON_DOTENV_DISABLED': '1', 'DJANGO_TESTING': 'True'})
        load_dotenv.assert_not_called()


def test_strict_prod_requires_redis_and_hardens_defaults(monkeypatch):
    with pytest.raises(ImproperlyConfigured, match='REDIS_CACHE_URL'):
        _load_settings(monkeypatch, {'DJANGO_DEBUG': 'False', 'DJANGO_TESTING': 'False'})

    prod = _load_settings(
        monkeypatch,
        {
            'DJANGO_DEBUG': 'False',
            'DJANGO_TESTING': 'False',
            'REDIS_CACHE_URL': 'redis://127.0.0.1:6379/1',
        },
    )
    assert 'testserver' not in prod['ALLOWED_HOSTS']
    assert prod['ALLOWED_HOSTS'] == []
    assert prod['CORS_ALLOWED_ORIGINS'] == []
    assert prod['CSRF_TRUSTED_ORIGINS'] == []
    assert prod['CACHES']['default']['BACKEND'] == 'django.core.cache.backends.redis.RedisCache'
    assert prod['SESSION_COOKIE_SECURE'] is True
    assert prod['CSRF_COOKIE_SECURE'] is True
    assert prod['SECURE_SSL_REDIRECT'] is True
    assert prod['SECURE_HSTS_SECONDS'] == 31536000
    assert prod['SECURE_HSTS_INCLUDE_SUBDOMAINS'] is True
    assert prod['SECURE_HSTS_PRELOAD'] is True
    assert 'rest_framework.renderers.BrowsableAPIRenderer' not in prod['REST_FRAMEWORK']['DEFAULT_RENDERER_CLASSES']
    assert prod['ENABLE_DOCS_IN_PROD'] is False


def test_testing_mode_and_logging_handlers(monkeypatch):
    test_cfg = _load_settings(
        monkeypatch,
        {
            'DJANGO_DEBUG': 'False',
            'DJANGO_TESTING': 'True',
            'ENABLE_DOCS_IN_PROD': 'True',
        },
    )
    assert 'testserver' in test_cfg['ALLOWED_HOSTS']
    assert test_cfg['CORS_ALLOWED_ORIGINS']
    assert test_cfg['CSRF_TRUSTED_ORIGINS']
    assert test_cfg['CACHES']['default']['BACKEND'] == 'django.core.cache.backends.locmem.LocMemCache'
    assert test_cfg['SESSION_COOKIE_SECURE'] is False
    assert test_cfg['ENABLE_DOCS_IN_PROD'] is True
    assert 'rest_framework.renderers.BrowsableAPIRenderer' not in test_cfg['REST_FRAMEWORK']['DEFAULT_RENDERER_CLASSES']

    handlers = test_cfg['LOGGING']['handlers']
    for name in ('file_errors', 'file_security'):
        assert handlers[name]['class'] == 'logging.handlers.RotatingFileHandler'
        assert handlers[name]['maxBytes'] == 10 * 1024 * 1024
        assert handlers[name]['backupCount'] == 5
        assert handlers[name]['delay'] is True

    debug_cfg = _load_settings(monkeypatch, {'DJANGO_DEBUG': 'True', 'DJANGO_TESTING': 'False'})
    assert 'rest_framework.renderers.BrowsableAPIRenderer' in debug_cfg['REST_FRAMEWORK']['DEFAULT_RENDERER_CLASSES']
    assert logging.handlers.RotatingFileHandler is not None


@pytest.mark.django_db
def test_health_check_executes_select_1_and_handles_failure(client, monkeypatch):
    res = client.get('/api/health/')
    assert res.status_code == 200
    assert res.json() == {'status': 'healthy', 'database': 'connected'}

    from config import urls as config_urls

    class BrokenConn:
        def cursor(self):
            raise RuntimeError('db down')

    monkeypatch.setattr(config_urls, 'connection', BrokenConn())
    res_down = client.get('/api/health/')
    assert res_down.status_code == 503
    assert res_down.json() == {'status': 'unhealthy', 'database': 'disconnected'}


def test_jwt_and_admin_session_defaults(monkeypatch):
    cfg = _load_settings(monkeypatch, {'DJANGO_TESTING': 'True'})
    assert cfg['SIMPLE_JWT']['ACCESS_TOKEN_LIFETIME'] == timedelta(minutes=30)
    assert cfg['SIMPLE_JWT']['REFRESH_TOKEN_LIFETIME'] == timedelta(hours=12)
    assert cfg['SIMPLE_JWT']['ROTATE_REFRESH_TOKENS'] is True
    assert cfg['SIMPLE_JWT']['BLACKLIST_AFTER_ROTATION'] is True
    assert cfg['SIMPLE_JWT']['CHECK_REVOKE_TOKEN'] is True
    assert cfg['JWT_MAX_SESSION_HOURS'] == 12
    assert cfg['SESSION_COOKIE_AGE'] == 43200
    assert cfg['SESSION_EXPIRE_AT_BROWSER_CLOSE'] is True


def test_jwt_refresh_days_fallback_and_explicit_overrides(monkeypatch):
    fallback_cfg = _load_settings(
        monkeypatch,
        {
            'DJANGO_TESTING': 'True',
            'JWT_REFRESH_DAYS': '2',
        },
    )
    assert fallback_cfg['SIMPLE_JWT']['REFRESH_TOKEN_LIFETIME'] == timedelta(hours=48)
    assert fallback_cfg['JWT_MAX_SESSION_HOURS'] == 48
    assert fallback_cfg['SESSION_COOKIE_AGE'] == 48 * 3600

    blank_hours_cfg = _load_settings(
        monkeypatch,
        {
            'DJANGO_TESTING': 'True',
            'JWT_REFRESH_HOURS': '   ',
            'JWT_REFRESH_DAYS': '1',
        },
    )
    assert blank_hours_cfg['SIMPLE_JWT']['REFRESH_TOKEN_LIFETIME'] == timedelta(hours=24)
    assert blank_hours_cfg['JWT_MAX_SESSION_HOURS'] == 24

    override_cfg = _load_settings(
        monkeypatch,
        {
            'DJANGO_TESTING': 'True',
            'JWT_ACCESS_MINUTES': '15',
            'JWT_REFRESH_HOURS': '6',
            'JWT_REFRESH_DAYS': '14',
            'JWT_MAX_SESSION_HOURS': '10',
            'JWT_ROTATE_REFRESH_TOKENS': 'False',
        },
    )
    assert override_cfg['SIMPLE_JWT']['ACCESS_TOKEN_LIFETIME'] == timedelta(minutes=15)
    assert override_cfg['SIMPLE_JWT']['REFRESH_TOKEN_LIFETIME'] == timedelta(hours=6)
    assert override_cfg['JWT_MAX_SESSION_HOURS'] == 10
    assert override_cfg['SIMPLE_JWT']['ROTATE_REFRESH_TOKENS'] is False
    assert override_cfg['SESSION_COOKIE_AGE'] == 10 * 3600
    assert override_cfg['SESSION_EXPIRE_AT_BROWSER_CLOSE'] is True

    refresh_only_cfg = _load_settings(
        monkeypatch,
        {
            'DJANGO_TESTING': 'True',
            'JWT_REFRESH_HOURS': '8',
        },
    )
    assert refresh_only_cfg['SIMPLE_JWT']['REFRESH_TOKEN_LIFETIME'] == timedelta(hours=8)
    assert refresh_only_cfg['JWT_MAX_SESSION_HOURS'] == 8
    assert refresh_only_cfg['SESSION_COOKIE_AGE'] == 8 * 3600
