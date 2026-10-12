from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, VehicleViewSet

router = DefaultRouter()
router.register('customers', CustomerViewSet, basename='customer')
router.register('vehicles', VehicleViewSet, basename='vehicle')

urlpatterns = [
    path('', include(router.urls)),
]
