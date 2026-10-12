from rest_framework import viewsets, filters
from apps.accounts.permissions import ReadOnlyOrManager
from .models import Service
from .serializers import ServiceSerializer

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all().order_by('service_name')
    serializer_class = ServiceSerializer
    permission_classes = [ReadOnlyOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['service_name', 'description']
    ordering_fields = ['price', 'service_name']

