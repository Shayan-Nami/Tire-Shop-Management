from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BrandViewSet, SizeViewSet, TireViewSet, StockMovementViewSet

router = DefaultRouter()
router.register('brands', BrandViewSet, basename='brand')
router.register('sizes', SizeViewSet, basename='size')
router.register('tires', TireViewSet, basename='tire')
router.register('stock-movements', StockMovementViewSet, basename='stock-movement')

urlpatterns = [
    path('', include(router.urls)),
]
