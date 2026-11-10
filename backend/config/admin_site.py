import math

from django.contrib.admin import AdminSite
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from utils.throttling import AdminLoginIPRateThrottle, AdminLoginUsernameRateThrottle


class ThrottledAdminSite(AdminSite):
    """Applies the API login rate limits (per IP and per username) to POSTs on /admin/login/."""

    @method_decorator(never_cache)
    def login(self, request, extra_context=None):
        if request.method == 'POST':
            waits = []
            for throttle in (AdminLoginIPRateThrottle(), AdminLoginUsernameRateThrottle()):
                if not throttle.allow_request(request, None):
                    waits.append(throttle.wait())
            if waits:
                wait = math.ceil(max((w for w in waits if w is not None), default=60))
                return HttpResponse(
                    f'تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً پس از {wait} ثانیه مجدداً تلاش نمایید.',
                    status=429,
                    content_type='text/plain; charset=utf-8',
                    headers={'Retry-After': str(wait)},
                )
        return super().login(request, extra_context)
