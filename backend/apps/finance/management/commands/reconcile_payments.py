from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from apps.invoices.models import SalesInvoice, PurchaseInvoice, PaymentStatus


class Command(BaseCommand):
    help = 'تطبیق و راستی‌آزمایی وضعیت پرداخت (payment_status) فاکتورهای فروش و خرید با مجموع اسناد مالی معتبر و گزارش مغایرت‌ها'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("در حال بررسی و تطبیق وضعیت پرداخت فاکتورها با دفاتر اسناد مالی..."))

        discrepancies = []
        with transaction.atomic():
            # ۱. بررسی فاکتورهای فروش
            sales_invoices = SalesInvoice.objects.all().order_by('sales_invoice_id')
            total_sales_count = sales_invoices.count()

            for inv in sales_invoices:
                valid_received = inv.receipts.filter(is_cancelled=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                valid_refunded = inv.refunds.filter(is_cancelled=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                effective_paid = max(Decimal('0.00'), valid_received - valid_refunded)
                net_amount = inv.net_amount

                if net_amount == Decimal('0.00'):
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

            # ۲. بررسی فاکتورهای خرید
            purchase_invoices = PurchaseInvoice.objects.all().order_by('purchase_invoice_id')
            total_purchase_count = purchase_invoices.count()

            for inv in purchase_invoices:
                valid_paid = inv.payments.filter(is_cancelled=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
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
