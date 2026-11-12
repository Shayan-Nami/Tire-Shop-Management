import logging
import runpy
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
