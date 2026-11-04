from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User

from django.db import transaction
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


@transaction.atomic
def set_password_and_revoke_tokens(user: User, password: str) -> None:
    user.set_password(password)
    user.save(update_fields=['password'])
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
