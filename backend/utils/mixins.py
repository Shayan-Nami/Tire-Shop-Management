from __future__ import annotations

from typing import Any

from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response


class ImmutableDocumentViewSetMixin:
    immutable_document_name = 'سند'

    def update(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed('PUT', detail=f'ویرایش مستقیم {self.immutable_document_name} مجاز نیست.')

    def partial_update(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed('PATCH', detail=f'ویرایش مستقیم {self.immutable_document_name} مجاز نیست.')

    def destroy(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        raise MethodNotAllowed('DELETE', detail=f'حذف مستقیم {self.immutable_document_name} مجاز نیست.')
