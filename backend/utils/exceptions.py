import logging
import math
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import Throttled
from django.db.models import ProtectedError
from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions as drf_exceptions

logger = logging.getLogger('apps')


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None and isinstance(exc, DjangoValidationError):
        if hasattr(exc, 'message_dict'):
            detail = exc.message_dict
        elif hasattr(exc, 'messages'):
            detail = exc.messages
        else:
            detail = [str(exc)]
        drf_exc = drf_exceptions.ValidationError(detail=detail)
        response = exception_handler(drf_exc, context)

    if response is None and isinstance(exc, ProtectedError):
        response = Response({
            'detail': 'امکان حذف این آیتم به دلیل وجود اسناد مالی یا سوابق وابسته در سیستم وجود ندارد.'
        }, status=status.HTTP_400_BAD_REQUEST)
    elif response is None and isinstance(exc, IntegrityError):
        logger.warning(f"Integrity error converted to 400: {exc}", exc_info=exc)
        response = Response({
            'detail': 'خطای یکپارچگی داده‌ها در پایگاه داده. لطفاً از عدم وجود داده‌های تکراری یا وابستگی‌های نامعتبر اطمینان حاصل فرمایید.'
        }, status=status.HTTP_400_BAD_REQUEST)
    elif response is None:
        from django.conf import settings
        logger.error(f"Unhandled Server Error: {exc}", exc_info=True)
        if not getattr(settings, 'DEBUG', False):
            response = Response({
                'detail': 'خطای غیرمنتظره در سرور رخ داده است. لطفاً با مدیر سیستم تماس بگیرید.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if response is not None and isinstance(exc, Throttled):
        wait = math.ceil(exc.wait) if exc.wait is not None else 60
        response.data = {
            'detail': f'تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً پس از {wait} ثانیه مجدداً تلاش نمایید.',
            'available_in_seconds': wait
        }


    if response is not None:
        if not (isinstance(response.data, dict) and 'success' in response.data and 'status_code' in response.data):
            custom_data = {
                'success': False,
                'status_code': response.status_code,
                'errors': response.data
            }
            response.data = custom_data

    return response
