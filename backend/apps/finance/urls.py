from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReceiptVoucherViewSet, PaymentVoucherViewSet, CustomerRefundVoucherViewSet

router = DefaultRouter()
router.register('receipts', ReceiptVoucherViewSet, basename='receipt-voucher')
router.register('payments', PaymentVoucherViewSet, basename='payment-voucher')
router.register('customer-refunds', CustomerRefundVoucherViewSet, basename='customer-refund-voucher')

urlpatterns = [
    path('', include(router.urls)),
]
