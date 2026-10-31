from decimal import Decimal
from datetime import datetime, time, timedelta
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField, OuterRef, Subquery, Value, Case, When, Q
from django.db.models.functions import Greatest, Coalesce
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from apps.accounts.permissions import IsManager
from apps.catalog.models import Tire, Brand
from apps.invoices.models import (
    SalesInvoice, SalesInvoiceTireItem, SalesReturn, SalesReturnItem,
    InvoiceStatus, PaymentStatus
)
from apps.finance.models import ReceiptVoucher, CustomerRefundVoucher
from utils.jalali import parse_jalali_or_gregorian_date
from utils.expressions import DecimalDivision
from .serializers import (
    DashboardStatsResponseSerializer, SalesByBrandItemSerializer,
    ProfitabilityItemSerializer, InventoryValueResponseSerializer,
    SalesByDateRangeResponseSerializer, SalesByDateQuerySerializer,
    SalesByBrandQuerySerializer
)

class DashboardStatsView(APIView):
    """
    آمار کلی و شاخص‌های کلیدی عملکرد (KPI) جهت نمایش در کارت‌های داشبورد اصلی با لحاظ مرجوعی‌ها
    """
    permission_classes = [IsManager]

    @extend_schema(responses={200: DashboardStatsResponseSerializer})
    def get(self, request):
        today = timezone.localdate()
        today_start = timezone.make_aware(datetime.combine(today, time.min))
        tomorrow_start = today_start + timedelta(days=1)

        today_sales_aggr = SalesInvoice.objects.filter(
            invoice_date__gte=today_start,
            invoice_date__lt=tomorrow_start,
            status=InvoiceStatus.CONFIRMED
        ).aggregate(total=Sum('total_amount'), count=Count('sales_invoice_id'))

        today_returns_total = SalesReturn.objects.filter(
            return_date__gte=today_start,
            return_date__lt=tomorrow_start,
            sales_invoice__status=InvoiceStatus.CONFIRMED,
        ).aggregate(total=Sum('total_refund_amount'))['total'] or Decimal('0.00')

        gross_sales = today_sales_aggr['total'] or Decimal('0.00')
        # محاسبه درآمد خالص روز با در نظر گرفتن کسر مرجوعی‌ها از ناخالص فروش
        today_revenue = gross_sales - today_returns_total
        today_invoices_count = today_sales_aggr['count'] or 0

        # محاسبه دقیق مطالبات معوق: برای هر فاکتور مجزا max(net_amount - دریافتی_خالص, 0)
        # تا مازاد پرداخت یا اضافه مرجوعی یک فاکتور، بدهی فاکتور دیگر را کسر نکند.
        # فاکتورهای لغوشده (CANCELLED) به طور کامل از محاسبات خارج هستند.
        returned_subquery = SalesReturn.objects.filter(
            sales_invoice=OuterRef('pk')
        ).values('sales_invoice').annotate(
            tot=Sum('total_refund_amount')
        ).values('tot')

        receipts_subquery = ReceiptVoucher.objects.filter(
            sales_invoice=OuterRef('pk'),
            is_cancelled=False
        ).values('sales_invoice').annotate(
            tot=Sum('amount')
        ).values('tot')

        refunds_subquery = CustomerRefundVoucher.objects.filter(
            sales_invoice=OuterRef('pk'),
            is_cancelled=False
        ).values('sales_invoice').annotate(
            tot=Sum('amount')
        ).values('tot')

        net_amount_expr = Greatest(
            F('total_amount') - Coalesce(Subquery(returned_subquery), Value(Decimal('0.00'))),
            Value(Decimal('0.00'))
        )
        effective_received_expr = Greatest(
            Coalesce(Subquery(receipts_subquery), Value(Decimal('0.00'))) -
            Coalesce(Subquery(refunds_subquery), Value(Decimal('0.00'))),
            Value(Decimal('0.00'))
        )
        remaining_debt_expr = Greatest(
            net_amount_expr - effective_received_expr,
            Value(Decimal('0.00'))
        )

        active_invoices = SalesInvoice.objects.filter(status=InvoiceStatus.CONFIRMED).annotate(
            debt=remaining_debt_expr
        ).filter(debt__gt=0)

        receivables_aggr = active_invoices.aggregate(
            total=Sum('debt'),
            count=Count('sales_invoice_id')
        )
        total_receivables = receivables_aggr['total'] or Decimal('0.00')
        unpaid_count = receivables_aggr['count'] or 0


        inventory_value_aggr = Tire.objects.filter(stock_quantity__gt=0).aggregate(
            total_value=Sum(
                ExpressionWrapper(F('stock_quantity') * F('purchase_price'), output_field=DecimalField(max_digits=18, decimal_places=2))
            ),
            total_tires_count=Sum('stock_quantity')
        )
        total_inventory_value = inventory_value_aggr['total_value'] or Decimal('0.00')
        total_tires_stock = inventory_value_aggr['total_tires_count'] or 0

        low_stock_count = Tire.objects.filter(stock_quantity__lte=F('min_stock_alert')).count()

        return Response({
            'today_revenue': float(today_revenue),
            'today_invoices_count': today_invoices_count,
            'total_receivables': float(total_receivables),
            'unpaid_invoices_count': unpaid_count,
            'total_inventory_value': float(total_inventory_value),
            'total_tires_stock': total_tires_stock,
            'low_stock_count': low_stock_count
        })

class SalesByBrandReportView(APIView):
    """گزارش تفکیکی فروش بر اساس برندهای لاستیک با کسر مرجوعی‌ها"""
    permission_classes = [IsManager]

    @extend_schema(parameters=[SalesByBrandQuerySerializer], responses={200: SalesByBrandItemSerializer(many=True)})
    def get(self, request):
        query_serializer = SalesByBrandQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        brand_id = query_serializer.validated_data.get('brand_id')
        queryset = SalesInvoiceTireItem.objects.filter(
            sales_invoice__status=InvoiceStatus.CONFIRMED
        )
        return_items_qs = SalesReturnItem.objects.filter(
            sales_return__sales_invoice__status=InvoiceStatus.CONFIRMED
        )

        if brand_id:
            queryset = queryset.filter(tire__brand_id=brand_id)
            return_items_qs = return_items_qs.filter(tire__brand_id=brand_id)

        sales_by_brand = queryset.values(
            brand_name=F('tire__brand__brand_name')
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(
                Case(
                    When(
                        sales_invoice__discount_percent__gt=0,
                        then=ExpressionWrapper(
                            F('quantity') * F('unit_price') * (
                                Decimal('1.00') - DecimalDivision(F('sales_invoice__discount_percent'), Decimal('100.00'))
                            ),
                            output_field=DecimalField(max_digits=18, decimal_places=2)
                        )
                    ),
                    When(
                        sales_invoice__discount_amount__gt=0,
                        then=Case(
                            When(
                                Q(sales_invoice__total_amount__gt=0) | Q(sales_invoice__discount_amount__gt=0),
                                then=ExpressionWrapper(
                                    DecimalDivision(
                                        F('quantity') * F('unit_price') * F('sales_invoice__total_amount'),
                                        F('sales_invoice__total_amount') + F('sales_invoice__discount_amount'),
                                    ),
                                    output_field=DecimalField(max_digits=18, decimal_places=2)
                                )
                            ),
                            default=Decimal('0.00'),
                            output_field=DecimalField(max_digits=18, decimal_places=2)
                        )
                    ),
                    default=ExpressionWrapper(
                        F('quantity') * F('unit_price'),
                        output_field=DecimalField(max_digits=18, decimal_places=2)
                    ),
                    output_field=DecimalField(max_digits=18, decimal_places=2)
                )
            )
        )

        returns_by_brand = {
            r['brand_name']: r
            for r in return_items_qs.values(
                brand_name=F('tire__brand__brand_name')
            ).annotate(
                ret_qty=Sum('quantity'),
                ret_rev=Sum('refund_amount')
            )
        }

        data = []
        for r in sales_by_brand:
            brand_name = r['brand_name']
            ret = returns_by_brand.get(brand_name, {})
            net_qty = max((r['total_quantity'] or 0) - (ret.get('ret_qty') or 0), 0)
            net_rev = max((r['total_revenue'] or Decimal('0.00')) - (ret.get('ret_rev') or Decimal('0.00')), Decimal('0.00'))
            data.append({
                'brand_name': brand_name,
                'total_quantity': net_qty,
                'total_revenue': float(net_rev)
            })

        data.sort(key=lambda x: (-x['total_revenue'], x['brand_name']))
        return Response(data)

class ProfitabilityReportView(APIView):
    """گزارش سودآوری تایرها بر اساس مابه‌التفاوت نرخ خرید و فروش با کسر مرجوعی‌ها و احتساب تخفیف فاکتور"""
    permission_classes = [IsManager]

    @extend_schema(responses={200: ProfitabilityItemSerializer(many=True)})
    def get(self, request):
        # تجمیع محاسبات در سطح پایگاه داده با ORM aggregation جهت بهینه‌سازی مصرف حافظه
        tire_stats_qs = SalesInvoiceTireItem.objects.filter(
            sales_invoice__status=InvoiceStatus.CONFIRMED
        ).values(
            'tire_id',
            'tire__tire_name',
            'tire__brand__brand_name',
            'tire__size__size_name',
        ).annotate(
            total_sold=Sum('quantity'),
            total_cost=Sum(
                ExpressionWrapper(
                    F('quantity') * F('unit_cost'),
                    output_field=DecimalField(max_digits=18, decimal_places=2)
                )
            ),
            total_revenue=Sum(
                Case(
                    When(
                        sales_invoice__discount_percent__gt=0,
                        then=ExpressionWrapper(
                            F('quantity') * F('unit_price') * (
                                Decimal('1.00') - DecimalDivision(F('sales_invoice__discount_percent'), Decimal('100.00'))
                            ),
                            output_field=DecimalField(max_digits=18, decimal_places=2)
                        )
                    ),
                    When(
                        sales_invoice__discount_amount__gt=0,
                        then=Case(
                            When(
                                Q(sales_invoice__total_amount__gt=0) | Q(sales_invoice__discount_amount__gt=0),
                                then=ExpressionWrapper(
                                    DecimalDivision(
                                        F('quantity') * F('unit_price') * F('sales_invoice__total_amount'),
                                        F('sales_invoice__total_amount') + F('sales_invoice__discount_amount'),
                                    ),
                                    output_field=DecimalField(max_digits=18, decimal_places=2)
                                )
                            ),
                            default=Decimal('0.00'),
                            output_field=DecimalField(max_digits=18, decimal_places=2)
                        )
                    ),
                    default=ExpressionWrapper(
                        F('quantity') * F('unit_price'),
                        output_field=DecimalField(max_digits=18, decimal_places=2)
                    ),
                    output_field=DecimalField(max_digits=18, decimal_places=2)
                )
            )
        )

        returns_by_tire = {
            r['tire_id']: r
            for r in SalesReturnItem.objects.filter(
                sales_return__sales_invoice__status=InvoiceStatus.CONFIRMED
            ).values('tire_id').annotate(
                ret_qty=Sum('quantity'),
                ret_revenue=Sum('refund_amount'),
                ret_cost=Sum(
                    ExpressionWrapper(F('quantity') * F('unit_cost'), output_field=DecimalField(max_digits=18, decimal_places=2))
                )
            )
        }

        data = []
        for r in tire_stats_qs:
            tid = r['tire_id']
            ret = returns_by_tire.get(tid, {})
            ret_qty = ret.get('ret_qty') or 0
            ret_rev = ret.get('ret_revenue') or Decimal('0.00')
            ret_cst = ret.get('ret_cost') or Decimal('0.00')

            net_sold = max((r['total_sold'] or 0) - ret_qty, 0)
            net_revenue = max((r['total_revenue'] or Decimal('0.00')) - ret_rev, Decimal('0.00'))
            net_cost = max((r['total_cost'] or Decimal('0.00')) - ret_cst, Decimal('0.00'))
            net_profit = net_revenue - net_cost

            data.append({
                'tire_id': tid,
                'tire_name': r['tire__tire_name'],
                'brand_name': r['tire__brand__brand_name'],
                'size_name': r['tire__size__size_name'],
                'total_sold': net_sold,
                'total_revenue': float(net_revenue),
                'total_cost': float(net_cost),
                'total_profit': float(net_profit),
            })

        data.sort(key=lambda x: x['total_profit'], reverse=True)
        return Response(data)

class InventoryValueReportView(APIView):
    """گزارش ارزش ریالی موجودی انبار بر اساس قیمت خرید"""
    permission_classes = [IsManager]

    @extend_schema(responses={200: InventoryValueResponseSerializer})
    def get(self, request):
        tires = Tire.objects.select_related('brand', 'size').filter(stock_quantity__gt=0).annotate(
            inventory_value=ExpressionWrapper(
                F('stock_quantity') * F('purchase_price'),
                output_field=DecimalField(max_digits=18, decimal_places=2)
            )
        ).order_by('-inventory_value')

        data = []
        total_val = Decimal('0.00')
        for t in tires:
            val = t.inventory_value or Decimal('0.00')
            total_val += val
            data.append({
                'tire_id': t.tire_id,
                'tire_name': t.tire_name,
                'brand_name': t.brand.brand_name,
                'size_name': t.size.size_name,
                'stock_quantity': t.stock_quantity,
                'purchase_price': float(t.purchase_price),
                'inventory_value': float(val)
            })

        return Response({
            'total_inventory_value': float(total_val),
            'items': data
        })

class SalesByDateRangeReportView(APIView):
    """گزارش فروش بر اساس بازه تاریخ میلادی / شمسی با احتساب مرجوعی‌ها (مبنای مرجوعی: تاریخ ثبت مرجوعی)"""
    permission_classes = [IsManager]

    @extend_schema(parameters=[SalesByDateQuerySerializer], responses={200: SalesByDateRangeResponseSerializer})
    def get(self, request):
        query_serializer = SalesByDateQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        start_date = query_serializer.validated_data.get('start_date')
        end_date = query_serializer.validated_data.get('end_date')

        parsed_start = parse_jalali_or_gregorian_date(start_date) if start_date else None
        parsed_end = parse_jalali_or_gregorian_date(end_date) if end_date else None

        invoices = SalesInvoice.objects.filter(status=InvoiceStatus.CONFIRMED)
        returns = SalesReturn.objects.filter(sales_invoice__status=InvoiceStatus.CONFIRMED)

        if parsed_start:
            invoices = invoices.filter(invoice_date__date__gte=parsed_start)
            returns = returns.filter(return_date__date__gte=parsed_start)

        if parsed_end:
            invoices = invoices.filter(invoice_date__date__lte=parsed_end)
            returns = returns.filter(return_date__date__lte=parsed_end)

        summary = invoices.aggregate(
            total_invoices=Count('sales_invoice_id'),
            total_sales_amount=Sum('total_amount')
        )
        total_refund = returns.aggregate(total=Sum('total_refund_amount'))['total'] or Decimal('0.00')
        gross_sales = summary['total_sales_amount'] or Decimal('0.00')
        net_sales = gross_sales - total_refund

        return Response({
            'total_invoices': summary['total_invoices'] or 0,
            'total_sales_amount': float(net_sales),
            'gross_sales_amount': float(gross_sales),
            'total_refund_amount': float(total_refund),
            'start_date': start_date,
            'end_date': end_date
        })

