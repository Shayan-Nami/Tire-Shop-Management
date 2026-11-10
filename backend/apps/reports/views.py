from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from apps.accounts.permissions import IsManager
from .services import dashboard_stats, sales_by_brand, profitability, inventory_value, sales_by_date
from .serializers import (
    DashboardStatsResponseSerializer, SalesByBrandItemSerializer,
    ProfitabilityItemSerializer, InventoryValueResponseSerializer,
    SalesByDateRangeResponseSerializer, SalesByDateQuerySerializer,
    SalesByBrandQuerySerializer
)

class DashboardStatsView(APIView):
    permission_classes = [IsManager]

    @extend_schema(responses={200: DashboardStatsResponseSerializer})
    def get(self, request):
        return Response(dashboard_stats())

class SalesByBrandReportView(APIView):
    permission_classes = [IsManager]

    @extend_schema(parameters=[SalesByBrandQuerySerializer], responses={200: SalesByBrandItemSerializer(many=True)})
    def get(self, request):
        query_serializer = SalesByBrandQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        brand_id = query_serializer.validated_data.get('brand_id')
        return Response(sales_by_brand(brand_id=brand_id))

class ProfitabilityReportView(APIView):
    permission_classes = [IsManager]

    @extend_schema(responses={200: ProfitabilityItemSerializer(many=True)})
    def get(self, request):
        return Response(profitability())

class InventoryValueReportView(APIView):
    permission_classes = [IsManager]

    @extend_schema(responses={200: InventoryValueResponseSerializer})
    def get(self, request):
        return Response(inventory_value())

class SalesByDateRangeReportView(APIView):
    permission_classes = [IsManager]

    @extend_schema(parameters=[SalesByDateQuerySerializer], responses={200: SalesByDateRangeResponseSerializer})
    def get(self, request):
        query_serializer = SalesByDateQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        start_date = query_serializer.validated_data.get('start_date')
        end_date = query_serializer.validated_data.get('end_date')

        return Response(sales_by_date(start_date=start_date, end_date=end_date))

