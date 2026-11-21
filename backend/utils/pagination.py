from __future__ import annotations

from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.settings import api_settings


class StandardResultsSetPagination(PageNumberPagination):
    page_size = api_settings.PAGE_SIZE or 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_page_size(self, request: Request) -> int | None:
        configured = api_settings.PAGE_SIZE
        if configured is not None:
            self.page_size = min(int(configured), self.max_page_size)
        return super().get_page_size(request)

    def get_paginated_response(self, data: Any) -> Response:
        assert self.page is not None
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })
