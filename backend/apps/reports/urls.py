from django.urls import path
from .views import (
    DashboardStatsView, SalesByBrandReportView, ProfitabilityReportView,
    InventoryValueReportView, SalesByDateRangeReportView
)

urlpatterns = [
    path('dashboard-stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('sales-by-brand/', SalesByBrandReportView.as_view(), name='sales-by-brand-report'),
    path('profitability/', ProfitabilityReportView.as_view(), name='profitability-report'),
    path('inventory-value/', InventoryValueReportView.as_view(), name='inventory-value-report'),
    path('sales-by-date/', SalesByDateRangeReportView.as_view(), name='sales-by-date-report'),
]
