from unittest.mock import patch

from django.core.cache import caches
from django.test import override_settings


def test_configured_redis_cache_can_read_without_missing_dependencies():
    with override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': 'redis://127.0.0.1:6379/0',
        },
    }):
        with patch('redis.Redis.get', return_value=None) as get:
            assert caches['default'].get('dependency-probe') is None
            get.assert_called_once()
