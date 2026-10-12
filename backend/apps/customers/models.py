from django.db import models
from django.core.validators import RegexValidator
from utils.persian import normalize_digits

phone_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message='شماره موبایل باید با 09 شروع شده و ۱۱ رقم باشد.'
)

national_code_validator = RegexValidator(
    regex=r'^\d{10}$',
    message='کد ملی باید ۱۰ رقم عددی باشد.'
)

class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100, verbose_name='نام و نام خانوادگی')
    phone_number = models.CharField(max_length=20, null=True, blank=True, validators=[phone_validator], verbose_name='شماره تماس')
    national_code = models.CharField(max_length=10, null=True, blank=True, validators=[national_code_validator], verbose_name='کد ملی')
    address = models.CharField(max_length=255, null=True, blank=True, verbose_name='آدرس')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ آخرین ویرایش')

    class Meta:
        db_table = 'Customer'
        verbose_name = 'مشتری'
        verbose_name_plural = 'مشتریان'
        constraints = [
            models.UniqueConstraint(
                fields=['phone_number'],
                name='unique_customer_phone_number_not_null',
                condition=models.Q(phone_number__isnull=False) & ~models.Q(phone_number='')
            ),
            models.UniqueConstraint(
                fields=['national_code'],
                name='unique_customer_national_code_not_null',
                condition=models.Q(national_code__isnull=False) & ~models.Q(national_code='')
            ),
        ]

    def clean_fields(self, exclude=None):
        if self.phone_number is not None:
            norm_p = normalize_digits(str(self.phone_number).strip())
            self.phone_number = norm_p if norm_p else None
        if self.national_code is not None:
            norm_nc = normalize_digits(str(self.national_code).strip())
            self.national_code = norm_nc if norm_nc else None
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.phone_number is not None:
            norm_p = normalize_digits(str(self.phone_number).strip())
            self.phone_number = norm_p if norm_p else None
            if self.phone_number:
                qs = Customer.objects.filter(phone_number=self.phone_number)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                if qs.exists():
                    raise ValidationError({'phone_number': 'این شماره تماس قبلاً برای مشتری دیگری ثبت شده است.'})
        if self.national_code is not None:
            norm_nc = normalize_digits(str(self.national_code).strip())
            self.national_code = norm_nc if norm_nc else None
            if self.national_code:
                qs = Customer.objects.filter(national_code=self.national_code)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                if qs.exists():
                    raise ValidationError({'national_code': 'این کد ملی قبلاً برای مشتری دیگری ثبت شده است.'})

    def save(self, *args, **kwargs):
        if self.phone_number is not None:
            norm_p = normalize_digits(str(self.phone_number).strip())
            self.phone_number = norm_p if norm_p else None
        if self.national_code is not None:
            norm_nc = normalize_digits(str(self.national_code).strip())
            self.national_code = norm_nc if norm_nc else None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"

class Vehicle(models.Model):
    vehicle_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='vehicles',
        verbose_name='مشتری'
    )
    license_plate = models.CharField(max_length=20, unique=True, verbose_name='شماره پلاک')
    model = models.CharField(max_length=100, verbose_name='مدل خودرو')
    year = models.CharField(max_length=10, blank=True, verbose_name='سال ساخت')
    tire_size_recommended = models.CharField(max_length=50, blank=True, verbose_name='سایز تایر پیشنهادی')
    notes = models.TextField(blank=True, verbose_name='توضیحات و سوابق فنی')

    class Meta:
        db_table = 'Vehicle'
        verbose_name = 'خودرو'
        verbose_name_plural = 'خودروها'

    def clean_fields(self, exclude=None):
        if self.license_plate:
            self.license_plate = normalize_digits(str(self.license_plate).strip())
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        if self.license_plate:
            self.license_plate = normalize_digits(str(self.license_plate).strip())

    def save(self, *args, **kwargs):
        if self.license_plate:
            self.license_plate = normalize_digits(str(self.license_plate).strip())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.model} - {self.license_plate} ({self.customer.full_name})"
