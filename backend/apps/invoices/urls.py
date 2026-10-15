from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SalesInvoiceViewSet, PurchaseInvoiceViewSet, SalesReturnViewSet

router = DefaultRouter()
router.register('sales', SalesInvoiceViewSet, basename='sales-invoice')
router.register('purchases', PurchaseInvoiceViewSet, basename='purchase-invoice')
router.register('returns', SalesReturnViewSet, basename='sales-return')


urlpatterns = [
    path('', include(router.urls)),
]
