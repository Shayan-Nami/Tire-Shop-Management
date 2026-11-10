from django.conf import settings
from django.core.checks import Tags, Warning, register

LOCMEM_BACKEND = 'django.core.cache.backends.locmem.LocMemCache'


@register(Tags.security, deploy=True)
def check_proxy_throttle_identity(app_configs, **kwargs):
    if settings.DEBUG or not settings.SECURE_PROXY_SSL_HEADER:
        return []
    if settings.REST_FRAMEWORK.get('NUM_PROXIES') != 0:
        return []
    return [Warning(
        'SECURE_PROXY_SSL_HEADER فعال است اما NUM_PROXIES برابر ۰ است.',
        hint=(
            'پشت پروکسی معکوس، همه کاربران یک IP مشترک دارند و سقف تلاش ورود برای همه یکسان می‌شود. '
            'NUM_PROXIES را برابر تعداد پروکسی‌های واقعی تنظیم کنید.'
        ),
        id='tireshop.W001',
    )]


@register(Tags.security, deploy=True)
def check_throttle_cache_is_shared(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    if settings.CACHES.get('default', {}).get('BACKEND') != LOCMEM_BACKEND:
        return []
    return [Warning(
        'کش پیش‌فرض از نوع LocMem است؛ شمارنده‌های محدودسازی درخواست و تلاش ورود برای هر پردازش جداگانه است.',
        hint=(
            'با چند worker (مثلاً gunicorn) سقف‌ها چندبرابر می‌شوند. '
            'برای کش مشترک REDIS_CACHE_URL را تنظیم کنید.'
        ),
        id='tireshop.W002',
    )]
