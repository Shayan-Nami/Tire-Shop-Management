from rest_framework import viewsets, filters
from .models import Supplier
from .serializers import SupplierSerializer
from apps.accounts.permissions import ReadOnlyOrWarehouse

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('supplier_name')
    serializer_class = SupplierSerializer
    permission_classes = [ReadOnlyOrWarehouse]
    filter_backends = [filters.SearchFilter]
    search_fields = ['supplier_name', 'phone_number', 'address']
