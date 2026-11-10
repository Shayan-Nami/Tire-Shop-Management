from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from apps.accounts.permissions import IsDocManagerOrDebug

admin.site.site_header = 'مدیریت فروشگاه و خدمات لاستیک'
admin.site.site_title = 'سامانه فروشگاه لاستیک'
admin.site.index_title = 'میز کار مدیریت سیستم'


def health_check_view(request):
    try:
        connection.ensure_connection()
        db_healthy = True
    except Exception:
        db_healthy = False
    return JsonResponse({
        'status': 'healthy' if db_healthy else 'unhealthy',
        'database': 'connected' if db_healthy else 'disconnected'
    }, status=200 if db_healthy else 503)


urlpatterns = [
    path('api/health/', health_check_view, name='health-check'),

    path('admin/', admin.site.urls),

    path('api/schema/', SpectacularAPIView.as_view(permission_classes=[IsDocManagerOrDebug]), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[IsDocManagerOrDebug]), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema', permission_classes=[IsDocManagerOrDebug]), name='redoc'),

    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/crm/', include('apps.customers.urls')),
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/workshop/', include('apps.services_app.urls')),
    path('api/v1/procurement/', include('apps.suppliers.urls')),
    path('api/v1/invoices/', include('apps.invoices.urls')),
    path('api/v1/treasury/', include('apps.finance.urls')),
    path('api/v1/analytics/', include('apps.reports.urls')),
]
