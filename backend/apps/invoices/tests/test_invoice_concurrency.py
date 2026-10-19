import threading
from decimal import Decimal
import pytest
from django.test import TransactionTestCase
from django.db import connection, models

from apps.accounts.models import User, UserRole
from apps.customers.models import Customer
from apps.catalog.models import Tire, Brand, Size, StockMovementType
from apps.invoices.models import (
    SalesInvoice, SalesInvoiceTireItem, InvoiceStatus, PaymentStatus
)
from apps.invoices.services import (
    create_sales_invoice_service,
    cancel_sales_invoice_service,
    create_sales_return_service,
)
from apps.finance.models import ReceiptVoucher, CustomerRefundVoucher
from apps.finance.services import (
    create_receipt_voucher_service,
    create_customer_refund_voucher_service,
)


@pytest.mark.skipif(
    connection.vendor == 'sqlite',
    reason="تست همروندی چندنخی و قفل ردیف (select_for_update) نیازمند پایگاه داده رابطه‌ای چندنخی (PostgreSQL) است."
)
class TestConcurrencyPostgres(TransactionTestCase):
    """
    مجموعه تست‌های جامع همروندی (Concurrency & Race Condition) روی پایگاه داده رابطه‌ای چندنخی (PostgreSQL).
    این آزمون‌ها سناریوهای رقابت نخ‌ها (Race Condition)، قفل‌های ردیفی (select_for_update)، و جلوگیری از بن‌بست (Deadlock Prevention)
    را با چندین Thread هم‌زمان و هماهنگ‌شده با Barrier می‌سنجند.
    """

    def setUp(self):
        super().setUp()
        self.manager = User.objects.create_user(
            username='manager_concurrency',
            password='Password123!',
            role=UserRole.MANAGER,
            full_name='مدیر تست همروندی',
            is_staff=True
        )
        self.customer = Customer.objects.create(
            full_name='مشتری تست همروندی',
            phone_number='09121119988'
        )
        self.brand_barez, _ = Brand.objects.get_or_create(brand_name='بارز')
        self.brand_yazd, _ = Brand.objects.get_or_create(brand_name='یزد')
        self.brand_kavir, _ = Brand.objects.get_or_create(brand_name='کویر')

        self.size_175, _ = Size.objects.get_or_create(size_name='175/70R13')
        self.size_205, _ = Size.objects.get_or_create(size_name='205/55R16')
        self.size_185, _ = Size.objects.get_or_create(size_name='185/65R14')
        self.size_205_60, _ = Size.objects.get_or_create(size_name='205/60R15')
        self.size_165, _ = Size.objects.get_or_create(size_name='165/65R13')
        self.size_195, _ = Size.objects.get_or_create(size_name='195/65R15')
        self.size_215, _ = Size.objects.get_or_create(size_name='215/60R16')

    def test_concurrent_sales_overselling_prevention(self):
        """
        سناریو ۱: جلوگیری از بیش‌فروشی (Overselling) در مرز موجودی.
        تایر با موجودی فقط ۱ حلقه؛ ۵ نخ به صورت هم‌زمان تلاش می‌کنند ۱ حلقه بخرند.
        نتیجه قطعی: دقیقاً ۱ فاکتور با موفقیت ثبت می‌شود، ۴ نخ دیگر با خطای عدم کفایت موجودی رد می‌شوند،
        و موجودی نهایی دقیقاً ۰ می‌گردد (هرگز منفی نمی‌شود).
        """
        tire = Tire.objects.create(
            tire_name='تایر همروندی ۱۷۵/۷۰R۱۳',
            size=self.size_175,
            brand=self.brand_barez,
            stock_quantity=1,
            purchase_price=Decimal('1000000'),
            sale_price=Decimal('1300000')
        )

        num_threads = 5
        barrier = threading.Barrier(num_threads)
        successes = []
        errors = []
        threads = []

        def worker():
            try:
                barrier.wait()
                invoice = create_sales_invoice_service(
                    customer=self.customer,
                    vehicle=None,
                    tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1300000')}],
                    service_items_data=[],
                    created_by=self.manager
                )
                successes.append(invoice.pk)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive(), "یک یا چند نخ در مهلت ۱۰ ثانیه‌ای به پایان نرسیدند!"

        tire.refresh_from_db()
        assert len(successes) == 1, f"انتظار دقیقاً ۱ فروش موفق، اما {len(successes)} ثبت شد!"
        assert len(errors) == num_threads - 1, f"انتظار {num_threads - 1} خطا، اما {len(errors)} دریافت شد!"
        assert tire.stock_quantity == 0, f"موجودی نهایی باید ۰ باشد، اما {tire.stock_quantity} است!"
        for err in errors:
            assert 'موجودی تایر' in str(err) and 'کافی نیست' in str(err)

    def test_concurrent_excess_customer_refunds_cap(self):
        """
        سناریو ۲: جلوگیری از رقابت در استرداد وجه به مشتری مازاد بر سقف پرداخت.
        فاکتوری با مبلغ ۱,۰۰۰,۰۰۰ تومان که کامل پرداخت شده، کالایی به ارزش ۴۰۰,۰۰۰ تومان مرجوع شده است.
        حداکثر مازاد قابل استرداد ۴۰۰,۰۰۰ تومان است. ۵ نخ به طور هم‌زمان درخواست استرداد ۴۰۰,۰۰۰ تومان دارند.
        نتیجه قطعی: دقیقاً ۱ سند استرداد صادر می‌شود و ۴ نخ دیگر رد می‌شوند. مجموع استرداد معتبر ۴۰۰,۰۰۰ تومان باقی می‌ماند.
        """
        tire = Tire.objects.create(
            tire_name='تایر تست استرداد',
            size=self.size_205,
            brand=self.brand_yazd,
            stock_quantity=10,
            purchase_price=Decimal('800000'),
            sale_price=Decimal('1000000')
        )
        invoice = create_sales_invoice_service(
            customer=self.customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000')}],
            service_items_data=[],
            created_by=self.manager
        )
        # ثبت پرداخت کامل فاکتور
        create_receipt_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('1000000'),
            user=self.manager
        )
        tire_item = invoice.tire_items.first()
        # ثبت مرجوعی کالا به ارزش ۱,۰۰۰,۰۰۰ (۱ قلم)
        sales_return = create_sales_return_service(
            invoice=invoice,
            reason='مرجوعی به علت تغییر نظر مشتری',
            items_data=[{'sales_invoice_tire_item_id': tire_item.pk, 'quantity': 1}],
            user=self.manager
        )
        # در این لحظه: دریافتی = ۱,۰۰۰,۰۰۰ ، خالص فاکتور = ۰ ، مازاد = ۱,۰۰۰,۰۰۰
        # ۵ نخ به طور همزمان درخواست استرداد کل مبلغ ۱,۰۰۰,۰۰۰ تومان می‌دهند
        num_threads = 5
        barrier = threading.Barrier(num_threads)
        successes = []
        errors = []
        threads = []

        def worker():
            try:
                barrier.wait()
                refund = create_customer_refund_voucher_service(
                    sales_invoice=invoice,
                    amount=Decimal('1000000'),
                    sales_return=sales_return,
                    user=self.manager
                )
                successes.append(refund.pk)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive(), "نخ در مهلت ۱۰ ثانیه‌ای به پایان نرسید!"

        assert len(successes) == 1, f"دقیقاً ۱ استرداد باید ثبت شود اما {len(successes)} ثبت شد!"
        assert len(errors) == num_threads - 1

        total_refunded = invoice.refunds.filter(is_cancelled=False).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        assert total_refunded == Decimal('1000000')

    def test_deadlock_prevention_reverse_ordered_tires(self):
        """
        سناریو ۳: پیشگیری قطعی از بن‌بست (Deadlock Prevention) با مرتب‌سازی صعودی شناسه تایرها.
        نخ ۱: اقلام را با ترتیب [تایر A, تایر B] ثبت می‌کند.
        نخ ۲: اقلام را با ترتیب معکوس [تایر B, تایر A] ثبت می‌کند.
        به دلیل مرتب‌سازی صعودی شناسه تایرها قبل از select_for_update در سرویس انبار، هیچ بن‌بستی رخ نمی‌دهد
        و هر دو فاکتور بدون بروز خطای Deadlock با موفقیت ذخیره می‌شوند.
        """
        tire_a = Tire.objects.create(
            tire_name='تایر آلفا ۱۸۵/۶۵R۱۴',
            size=self.size_185,
            brand=self.brand_kavir,
            stock_quantity=10,
            purchase_price=Decimal('500000'),
            sale_price=Decimal('700000')
        )
        tire_b = Tire.objects.create(
            tire_name='تایر بتا ۲۰۵/۶۰R۱۵',
            size=self.size_205_60,
            brand=self.brand_barez,
            stock_quantity=10,
            purchase_price=Decimal('600000'),
            sale_price=Decimal('850000')
        )

        barrier = threading.Barrier(2)
        successes = []
        errors = []
        threads = []

        def worker_forward():
            try:
                barrier.wait()
                inv = create_sales_invoice_service(
                    customer=self.customer,
                    vehicle=None,
                    tire_items_data=[
                        {'tire': tire_a, 'quantity': 1, 'unit_price': Decimal('700000')},
                        {'tire': tire_b, 'quantity': 1, 'unit_price': Decimal('850000')},
                    ],
                    service_items_data=[],
                    created_by=self.manager
                )
                successes.append(inv.pk)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        def worker_reverse():
            try:
                barrier.wait()
                inv = create_sales_invoice_service(
                    customer=self.customer,
                    vehicle=None,
                    tire_items_data=[
                        {'tire': tire_b, 'quantity': 1, 'unit_price': Decimal('850000')},
                        {'tire': tire_a, 'quantity': 1, 'unit_price': Decimal('700000')},
                    ],
                    service_items_data=[],
                    created_by=self.manager
                )
                successes.append(inv.pk)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        t1 = threading.Thread(target=worker_forward)
        t2 = threading.Thread(target=worker_reverse)
        threads = [t1, t2]
        t1.start()
        t2.start()

        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive(), "احتمال بروز بن‌بست (Deadlock)! نخ‌ها در مهلت زمانی پایان نیافتند."

        assert len(errors) == 0, f"خطایی رخ داد: {errors}"
        assert len(successes) == 2

        tire_a.refresh_from_db()
        tire_b.refresh_from_db()
        assert tire_a.stock_quantity == 8
        assert tire_b.stock_quantity == 8

    def test_concurrent_invoice_number_generation_sequential_and_gapless(self):
        """
        سناریو ۴: تولید شماره فاکتور پیوسته و یکتا در همروندی ۱۰ نخ.
        ۱۰ نخ هم‌زمان اقدام به صدور فاکتور فروش می‌کنند.
        تمام ۱۰ فاکتور شماره‌های یکتا و کاملاً متوالی و بدون پرش (Gapless) دریافت می‌کنند.
        """
        tire = Tire.objects.create(
            tire_name='تایر شماره‌گذاری ۱۶۵/۶۵R۱۳',
            size=self.size_165,
            brand=self.brand_yazd,
            stock_quantity=50,
            purchase_price=Decimal('400000'),
            sale_price=Decimal('600000')
        )

        num_threads = 10
        barrier = threading.Barrier(num_threads)
        invoice_numbers = []
        errors = []
        threads = []

        def worker():
            try:
                barrier.wait()
                inv = create_sales_invoice_service(
                    customer=self.customer,
                    vehicle=None,
                    tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('600000')}],
                    service_items_data=[],
                    created_by=self.manager
                )
                invoice_numbers.append(inv.invoice_number)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive(), "نخ در مهلت ۱۰ ثانیه‌ای پایان نیافت!"

        assert len(errors) == 0, f"خطایی رخ داد: {errors}"
        assert len(invoice_numbers) == num_threads
        assert len(set(invoice_numbers)) == num_threads, "شماره فاکتورهای تکراری تولید شده است!"

        # استخراج ۵ رقم انتهای شماره‌ها برای بررسی پیوستگی
        seq_nums = sorted([int(num.split('-')[-1]) for num in invoice_numbers])
        for i in range(len(seq_nums) - 1):
            assert seq_nums[i + 1] == seq_nums[i] + 1, f"پیوستگی شماره‌ها شکسته شد: {seq_nums}"

    def test_concurrent_return_vs_invoice_cancellation(self):
        """
        سناریو ۵: تداخل لغو فاکتور در برابر ثبت مرجوعی فروش.
        نخ ۱: قصد لغو فاکتور فروش را دارد.
        نخ ۲: هم‌زمان قصد ثبت مرجوعی فروش برای همان فاکتور را دارد.
        نتیجه قطعی: یکی از دو عملیات اول قفل را گرفته و ثبت می‌شود و دیگری با پیام اعتبارسنجی شفاف و معتبر رد می‌شود؛
        هیچگاه وضعیت نامعتبر یا ناسازگاری مالی/انباری در دیتابیس به وجود نمی‌آید.
        """
        tire = Tire.objects.create(
            tire_name='تایر تست لغو و مرجوعی',
            size=self.size_195,
            brand=self.brand_barez,
            stock_quantity=10,
            purchase_price=Decimal('600000'),
            sale_price=Decimal('900000')
        )
        invoice = create_sales_invoice_service(
            customer=self.customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('900000')}],
            service_items_data=[],
            created_by=self.manager
        )
        tire_item = invoice.tire_items.first()

        barrier = threading.Barrier(2)
        results = []
        threads = []

        def worker_cancel():
            try:
                barrier.wait()
                cancel_sales_invoice_service(invoice=invoice, user=self.manager)
                results.append(('cancel', True, None))
            except Exception as exc:
                results.append(('cancel', False, exc))
            finally:
                connection.close()

        def worker_return():
            try:
                barrier.wait()
                create_sales_return_service(
                    invoice=invoice,
                    reason='مرجوعی کالا در همروندی',
                    items_data=[{'sales_invoice_tire_item_id': tire_item.pk, 'quantity': 1}],
                    user=self.manager
                )
                results.append(('return', True, None))
            except Exception as exc:
                results.append(('return', False, exc))
            finally:
                connection.close()

        t1 = threading.Thread(target=worker_cancel)
        t2 = threading.Thread(target=worker_return)
        threads = [t1, t2]
        t1.start()
        t2.start()

        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive()

        successes = [r for r in results if r[1] is True]
        failures = [r for r in results if r[1] is False]

        assert len(successes) == 1, f"دقیقاً یکی از دو عملیات باید پیروز شود: {results}"
        assert len(failures) == 1

        invoice.refresh_from_db()
        if successes[0][0] == 'cancel':
            assert invoice.status == InvoiceStatus.CANCELLED
            assert not invoice.returns.exists()
            assert 'امکان ثبت مرجوعی برای فاکتور لغو شده وجود ندارد' in str(failures[0][2])
        else:
            assert invoice.status == InvoiceStatus.CONFIRMED
            assert invoice.returns.count() == 1
            assert 'امکان لغو فاکتوری که برای آن سند مرجوعی ثبت شده وجود ندارد' in str(failures[0][2])

    def test_concurrent_receipt_vouchers_balance_cap(self):
        """
        سناریو ۶: سقف دریافت وجه در همروندی اسناد دریافت.
        فاکتوری به مبلغ ۱,۵۰۰,۰۰۰ تومان بدون پرداختی.
        ۵ نخ هم‌زمان تلاش می‌کنند سند دریافت به مبلغ ۱,۵۰۰,۰۰۰ تومان ثبت کنند.
        نتیجه قطعی: دقیقاً ۱ نخ موفق می‌شود، ۴ نخ دیگر با خطای پر شدن سقف یا مازاد رد می‌شوند،
        و جمع کل اسناد دریافت معتبر فاکتور دقیقاً ۱,۵۰۰,۰۰۰ تومان و وضعیت فاکتور PAID می‌شود.
        """
        tire = Tire.objects.create(
            tire_name='تایر تست دریافت همروند',
            size=self.size_215,
            brand=self.brand_kavir,
            stock_quantity=10,
            purchase_price=Decimal('1000000'),
            sale_price=Decimal('1500000')
        )
        invoice = create_sales_invoice_service(
            customer=self.customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1500000')}],
            service_items_data=[],
            created_by=self.manager
        )

        num_threads = 5
        barrier = threading.Barrier(num_threads)
        successes = []
        errors = []
        threads = []

        def worker():
            try:
                barrier.wait()
                voucher = create_receipt_voucher_service(
                    sales_invoice=invoice,
                    amount=Decimal('1500000'),
                    user=self.manager
                )
                successes.append(voucher.pk)
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()

        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)
            assert not t.is_alive()

        assert len(successes) == 1, f"دقیقاً ۱ دریافت باید موفق شود اما {len(successes)} موفق شد!"
        assert len(errors) == num_threads - 1

        total_received = invoice.receipts.filter(is_cancelled=False).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        assert total_received == Decimal('1500000')

        invoice.refresh_from_db()
        assert invoice.payment_status == PaymentStatus.PAID
