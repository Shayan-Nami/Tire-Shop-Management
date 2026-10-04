from rest_framework.throttling import SimpleRateThrottle


class LoginIPRateThrottle(SimpleRateThrottle):
    """
    محدودسازی نرخ تلاش برای ورود بر اساس آدرس IP کلاینت (حداکثر ۵ درخواست در دقیقه)
    جهت جلوگیری از حملات Brute-Force توزیع‌نشده
    """
    scope = 'login_ip'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }


class LoginUsernameRateThrottle(SimpleRateThrottle):
    """
    محدودسازی نرخ تلاش برای ورود بر اساس نام کاربری / شماره همراه ورودی (حداکثر ۵ درخواست در دقیقه)
    جهت مقابله با حملات Brute-Force توزیع‌شده (از IPهای متعدد علیه یک حساب مشخص)
    """
    scope = 'login_username'

    def get_cache_key(self, request, view):
        # بررسی نوع داده ورودی جهت اطمینان از ساختار معتبر دیکشنری
        if not hasattr(request, 'data') or not isinstance(request.data, dict):
            return None
        username = request.data.get('username') or request.data.get('phone_number')
        if not username:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': str(username).strip().lower()
        }


class TokenRefreshRateThrottle(SimpleRateThrottle):
    """
    محدودسازی نرخ تمدید توکن JWT در اندپوینت refresh (حداکثر ۱۵ درخواست در دقیقه)
    """
    scope = 'token_refresh'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
