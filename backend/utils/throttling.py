from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Any

from rest_framework.throttling import SimpleRateThrottle


class LoginIPRateThrottle(SimpleRateThrottle):
    scope = 'login_ip'

    def get_cache_key(self, request: Any, view: Any) -> str:
        return str(
            self.cache_format % {
                'scope': self.scope,
                'ident': self.get_ident(request),
            }
        )


class LoginUsernameRateThrottle(SimpleRateThrottle):
    scope = 'login_username'

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        data = getattr(request, 'data', None)
        if not isinstance(data, Mapping):
            return None
        username = data.get('username') or data.get('phone_number')
        if not username:
            return None
        normalized = str(username).strip().lower()
        if not normalized:
            return None
        username_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        return str(
            self.cache_format % {
                'scope': self.scope,
                'ident': username_hash,
            }
        )


class TokenRefreshRateThrottle(SimpleRateThrottle):
    scope = 'token_refresh'

    def get_cache_key(self, request: Any, view: Any) -> str:
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            ident: Any = user.pk
        else:
            ident = self.get_ident(request)
        return str(
            self.cache_format % {
                'scope': self.scope,
                'ident': ident,
            }
        )
