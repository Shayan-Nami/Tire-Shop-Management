from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.db.models import F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Greatest
from apps.finance.models import CustomerRefundVoucher, PaymentVoucher, ReceiptVoucher
from apps.invoices.models import InvoiceStatus, PaymentStatus, PurchaseInvoice, SalesInvoice, SalesReturn


class Command(BaseCommand):
    help = 'تطبیق و راستی‌آزمایی وضعیت پرداخت (payment_status) فاکتورهای فروش و خرید با مجموع اسناد مالی معتبر و گزارش مغایرت‌ها'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("در حال بررسی و تطبیق وضعیت پرداخت فاکتورها با دفاتر اسناد مالی..."))

        money_field = models.DecimalField(max_digits=14, decimal_places=2)
        zero_val = Value(Decimal('0.00'), output_field=money_field)

        returned_subquery = SalesReturn.objects.filter(
            sales_invoice=OuterRef('pk')
        ).values('sales_invoice').annotate(total=Sum('total_refund_amount')).values('total')

        receipts_subquery = ReceiptVoucher.objects.filter(
            sales_invoice=OuterRef('pk'),
            is_cancelled=False,
        ).values('sales_invoice').annotate(total=Sum('amount')).values('total')

        refunds_subquery = CustomerRefundVoucher.objects.filter(
            sales_invoice=OuterRef('pk'),
            is_cancelled=False,
        ).values('sales_invoice').annotate(total=Sum('amount')).values('total')

        payments_subquery = PaymentVoucher.objects.filter(
            purchase_invoice=OuterRef('pk'),
            is_cancelled=False,
        ).values('purchase_invoice').annotate(total=Sum('amount')).values('total')

        discrepancies = []
        with transaction.atomic():
            sales_invoices = list(
                SalesInvoice.objects.select_related('customer').annotate(
                    returned_amount_annotated=Coalesce(
                        Subquery(returned_subquery, output_field=money_field),
                        zero_val,
                    ),
                    net_amount_annotated=Greatest(
                        F('total_amount') - Coalesce(Subquery(returned_subquery, output_field=money_field), zero_val),
                        zero_val,
                        output_field=money_field,
                    ),
                    valid_received_annotated=Coalesce(
                        Subquery(receipts_subquery, output_field=money_field),
                        zero_val,
                    ),
                    valid_refunded_annotated=Coalesce(
                        Subquery(refunds_subquery, output_field=money_field),
                        zero_val,
                    ),
                ).order_by('sales_invoice_id')
            )
            total_sales_count = len(sales_invoices)

            for inv in sales_invoices:
                valid_received = inv.valid_received_annotated or Decimal('0.00')
                valid_refunded = inv.valid_refunded_annotated or Decimal('0.00')
                effective_paid = max(Decimal('0.00'), valid_received - valid_refunded)
                net_amount = inv.net_amount

                if inv.status == InvoiceStatus.DRAFT:
                    expected_status = PaymentStatus.UNPAID
                elif net_amount == Decimal('0.00'):
                    expected_status = PaymentStatus.PAID
                elif effective_paid == Decimal('0.00'):
                    expected_status = PaymentStatus.UNPAID
                elif effective_paid < net_amount:
                    expected_status = PaymentStatus.PARTIAL
                else:
                    expected_status = PaymentStatus.PAID

                if inv.payment_status != expected_status:
                    discrepancies.append({
                        'type': 'فروش',
                        'id': inv.sales_invoice_id,
                        'party': inv.customer.full_name if inv.customer else 'بدون مشتری',
                        'net_amount': net_amount,
                        'paid_amount': effective_paid,
                        'stored_status': inv.payment_status,
                        'expected_status': expected_status,
                    })

            purchase_invoices = list(
                PurchaseInvoice.objects.select_related('supplier').annotate(
                    valid_paid_annotated=Coalesce(
                        Subquery(payments_subquery, output_field=money_field),
                        zero_val,
                    ),
                ).order_by('purchase_invoice_id')
            )
            total_purchase_count = len(purchase_invoices)

            for inv in purchase_invoices:
                valid_paid = inv.valid_paid_annotated or Decimal('0.00')
                total_amount = inv.total_amount

                if total_amount == Decimal('0.00') or valid_paid >= total_amount:
                    expected_status = PaymentStatus.PAID
                elif valid_paid > Decimal('0.00'):
                    expected_status = PaymentStatus.PARTIAL
                else:
                    expected_status = PaymentStatus.UNPAID

                if inv.payment_status != expected_status:
                    discrepancies.append({
                        'type': 'خرید',
                        'id': inv.purchase_invoice_id,
                        'party': inv.supplier.supplier_name if inv.supplier else 'بدون تامین‌کننده',
                        'net_amount': total_amount,
                        'paid_amount': valid_paid,
                        'stored_status': inv.payment_status,
                        'expected_status': expected_status,
                    })

        if discrepancies:
            self.stdout.write(self.style.ERROR("=" * 100))
            self.stdout.write(self.style.ERROR(f"هشدار: تعداد {len(discrepancies)} مغایرت در وضعیت پرداخت فاکتورها مشاهده شد!"))
            self.stdout.write(self.style.ERROR("=" * 100))
            header = f"{'نوع':<6} | {'شناسه':<8} | {'مبلغ خالص':<14} | {'پرداخت معتبر':<14} | {'وضعیت ذخیره‌شده':<16} | {'وضعیت محاسباتی':<16} | {'طرف حساب'}"
            self.stdout.write(header)
            self.stdout.write("-" * 100)
            for d in discrepancies:
                row = (
                    f"{d['type']:<6} | {d['id']:<8} | {d['net_amount']:<14,.0f} | "
                    f"{d['paid_amount']:<14,.0f} | {d['stored_status']:<16} | "
                    f"{d['expected_status']:<16} | {d['party']}"
                )
                self.stdout.write(self.style.WARNING(row))
            self.stdout.write("-" * 100)
            self.stdout.write(self.style.NOTICE("این ابزار فقط‌خواندنی است. وضعیت‌های ثبت‌شده باید از طریق سرویس‌های مالی اصلاح گردند."))
            raise CommandError(f"تطبیق پرداخت‌ها با شکست مواجه شد. {len(discrepancies)} مغایرت در وضعیت پرداخت یافت شد.")

        self.stdout.write(
            self.style.SUCCESS(
                f"تطبیق پرداخت‌ها با موفقیت انجام شد: وضعیت تمامی {total_sales_count} فاکتور فروش و {total_purchase_count} فاکتور خرید کاملاً منطبق است (۰ مغایرت)."
            )
        )
