from rest_framework.throttling import SimpleRateThrottle


class LoginIPRateThrottle(SimpleRateThrottle):
    scope = 'login_ip'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }


class LoginUsernameRateThrottle(SimpleRateThrottle):
    scope = 'login_username'

    def get_cache_key(self, request, view):
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
