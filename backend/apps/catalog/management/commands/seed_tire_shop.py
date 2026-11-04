from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.accounts.models import UserRole
from apps.catalog.models import Brand, Size, Tire, StockMovement
from apps.services_app.models import Service
from apps.customers.models import Customer, Vehicle
from apps.suppliers.models import Supplier
from apps.invoices.services import create_sales_invoice_service

User = get_user_model()

class Command(BaseCommand):
    help = 'ایجاد اطلاعات اولیه و داده‌های نمونه استاندارد فروشگاه لاستیک'

    def handle(self, *args, **options):
        if not settings.DEBUG or not getattr(settings, 'ALLOW_DEMO_SEED', False):
            raise CommandError('Demo seeding requires DEBUG=True and ALLOW_DEMO_SEED=True.')

        self.stdout.write("در حال ایجاد کاربران اولیه...")
        # کاربران پیش‌فرض با ۳ نقش
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'full_name': 'مدیر فروشگاه',
                'role': UserRole.MANAGER,
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save(update_fields=['password'])

        tech_user, created = User.objects.get_or_create(
            username='technician',
            defaults={
                'full_name': 'رضا تکنسین',
                'role': UserRole.TECHNICIAN,
                'is_staff': True
            }
        )
        if created:
            tech_user.set_password('tech123')
            tech_user.save(update_fields=['password'])

        wh_user, created = User.objects.get_or_create(
            username='warehouse',
            defaults={
                'full_name': 'محمد انباردار',
                'role': UserRole.WAREHOUSE,
                'is_staff': True
            }
        )
        if created:
            wh_user.set_password('warehouse123')
            wh_user.save(update_fields=['password'])

        self.stdout.write("در حال ایجاد برندها و سایزهای تایر...")
        # برندها
        barez, _ = Brand.objects.get_or_create(brand_name='بارز')
        kavir, _ = Brand.objects.get_or_create(brand_name='کویر تایر')
        yazd, _ = Brand.objects.get_or_create(brand_name='یزد تایر')
        michelin, _ = Brand.objects.get_or_create(brand_name='میشلن (Michelin)')
        hankook, _ = Brand.objects.get_or_create(brand_name='هانکوک (Hankook)')

        # سایزها
        s13, _ = Size.objects.get_or_create(size_name='165/65R13')
        s14, _ = Size.objects.get_or_create(size_name='185/65R14')
        s15, _ = Size.objects.get_or_create(size_name='185/65R15')
        s16, _ = Size.objects.get_or_create(size_name='205/55R16')

        # تایرها
        t1, _ = Tire.objects.get_or_create(
            tire_name='بارز پریمیوم گریپ P648',
            brand=barez,
            size=s14,
            defaults={
                'stock_quantity': 24,
                'purchase_price': Decimal('2200000'),
                'sale_price': Decimal('2750000'),
                'min_stock_alert': 8
            }
        )

        t2, _ = Tire.objects.get_or_create(
            tire_name='کویر تایر رادیال استار KB22',
            brand=kavir,
            size=s13,
            defaults={
                'stock_quantity': 16,
                'purchase_price': Decimal('1800000'),
                'sale_price': Decimal('2300000'),
                'min_stock_alert': 6
            }
        )

        t3, _ = Tire.objects.get_or_create(
            tire_name='یزد تایر مرکوری اسپورتی',
            brand=yazd,
            size=s15,
            defaults={
                'stock_quantity': 4,  # هشدار کمبود موجودی
                'purchase_price': Decimal('2400000'),
                'sale_price': Decimal('3000000'),
                'min_stock_alert': 6
            }
        )

        t4, _ = Tire.objects.get_or_create(
            tire_name='هانکوک اوپتیمو کره‌ای K424',
            brand=hankook,
            size=s16,
            defaults={
                'stock_quantity': 12,
                'purchase_price': Decimal('5500000'),
                'sale_price': Decimal('6800000'),
                'min_stock_alert': 4
            }
        )
        for t in [t1, t2, t3, t4]:
            if t.stock_quantity > 0 and not t.stock_movements.exists():
                StockMovement.objects.create(
                    tire=t,
                    quantity=t.stock_quantity,
                    movement_type='INITIAL_STOCK',
                    balance_after=t.stock_quantity,
                    unit_cost=t.purchase_price,
                    description='موجودی اولیه سید دیتابیس'
                )

        self.stdout.write("در حال ایجاد خدمات و تعرفه‌ها...")
        # خدمات
        srv1, _ = Service.objects.get_or_create(
            service_name='تعویض و جا انداختن هر حلقه لاستیک',
            defaults={'price': Decimal('80000'), 'description': 'شامل باز و بست چرخ و سوار کردن تایر'}
        )
        srv2, _ = Service.objects.get_or_create(
            service_name='بالانس چرخ کامپیوتری دیجیتال',
            defaults={'price': Decimal('100000'), 'description': 'بالانس درجا با سرب چسبی'}
        )
        srv3, _ = Service.objects.get_or_create(
            service_name='تنظیم باد با گاز نیتروژن (۴ چرخ)',
            defaults={'price': Decimal('150000'), 'description': 'تخلیه کامل باد معمولی و تزریق نیتروژن خالص'}
        )
        srv4, _ = Service.objects.get_or_create(
            service_name='آپارات گرم و پنچرگیری تیوبلس',
            defaults={'price': Decimal('120000'), 'description': 'ترمیم سوراخ با چسب و فتیله نسوز'}
        )

        self.stdout.write("در حال ایجاد تأمین‌کنندگان...")
        sup1, _ = Supplier.objects.get_or_create(
            supplier_name='شرکت پخش لاستیک البرز',
            defaults={'phone_number': '02188990011', 'address': 'تهران، خیابان چراغ برق، پلاک ۱۲۰'}
        )
        sup2, _ = Supplier.objects.get_or_create(
            supplier_name='نمایندگی رسمی بارز آذربایجان',
            defaults={'phone_number': '04133445566', 'address': 'تبریز، جاده آذرشهر، مجتمع تایر ایران'}
        )

        self.stdout.write("در حال ثبت مشتریان و خودروها...")
        c1, _ = Customer.objects.get_or_create(
            phone_number='09141122334',
            defaults={
                'full_name': 'مهندس علی افشار',
                'national_code': '1361234567',
                'address': 'تبریز، رشدیه، خیابان سروستان'
            }
        )
        v1, _ = Vehicle.objects.get_or_create(
            license_plate='12ب345-ایران11',
            defaults={
                'customer': c1,
                'model': 'پژو 206 تیپ 5',
                'year': '1399',
                'tire_size_recommended': '185/65R14'
            }
        )

        c2, _ = Customer.objects.get_or_create(
            phone_number='09129876543',
            defaults={
                'full_name': 'خانم سارا کریمی',
                'national_code': '0029876543',
                'address': 'تهران، سعادت‌آباد'
            }
        )
        v2, _ = Vehicle.objects.get_or_create(
            license_plate='68ج987-ایران22',
            defaults={
                'customer': c2,
                'model': 'دنا پلاس توربو اتوماتیک',
                'year': '1401',
                'tire_size_recommended': '205/55R16'
            }
        )

        # ایجاد یک فاکتور فروش نمونه برای تست اولیه
        if not c1.sales_invoices.exists():
            self.stdout.write("در حال صدور یک فاکتور فروش نمونه با تراکنش اتمیک...")
            create_sales_invoice_service(
                customer=c1,
                vehicle=v1,
                tire_items_data=[{'tire': t1, 'quantity': 2, 'unit_price': t1.sale_price}],
                service_items_data=[
                    {'service': srv1, 'quantity': 2, 'unit_price': srv1.price},
                    {'service': srv2, 'quantity': 2, 'unit_price': srv2.price}
                ],
                discount_amount=Decimal('50000'),
                payment_status='PAID',
                notes='مشتری خوش‌حساب - تعویض دو حلقه تایر جلو',
                created_by=admin_user
            )

        self.stdout.write(self.style.SUCCESS('اطلاعات اولیه با موفقیت در دیتابیس ثبت شد!'))
        self.stdout.write('Demo accounts: admin, technician, warehouse. Existing passwords were left unchanged.')
