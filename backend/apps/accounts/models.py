from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from utils.persian import normalize_digits

phone_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message='شماره موبایل باید با 09 شروع شده و ۱۱ رقم باشد.'
)

class UserRole(models.TextChoices):
    MANAGER = 'MANAGER', 'مدیر سیستم'
    TECHNICIAN = 'TECHNICIAN', 'تکنسین فنی'
    WAREHOUSE = 'WAREHOUSE', 'انباردار'

class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.TECHNICIAN,
        verbose_name='نقش کاربر'
    )
    full_name = models.CharField(max_length=150, blank=True, verbose_name='نام و نام خانوادگی')
    phone_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        validators=[phone_validator],
        verbose_name='شماره موبایل'
    )

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'
        db_table = 'Users'
        constraints = [
            models.UniqueConstraint(
                fields=['phone_number'],
                name='unique_user_phone_number_not_null',
                condition=models.Q(phone_number__isnull=False) & ~models.Q(phone_number='')
            )
        ]

    def clean_fields(self, exclude=None):
        if self.phone_number is not None:
            norm = normalize_digits(str(self.phone_number).strip())
            self.phone_number = norm if norm else None
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.phone_number is not None:
            norm = normalize_digits(str(self.phone_number).strip())
            self.phone_number = norm if norm else None
            if self.phone_number:
                qs = User.objects.filter(phone_number=self.phone_number)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                if qs.exists():
                    raise ValidationError({'phone_number': 'این شماره موبایل قبلاً برای کاربر دیگری ثبت شده است.'})

    def save(self, *args, **kwargs):
        if self.phone_number is not None:
            norm = normalize_digits(str(self.phone_number).strip())
            self.phone_number = norm if norm else None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name or self.username} ({self.get_role_display()})"

    @property
    def is_manager(self):
        return self.role == UserRole.MANAGER or self.is_superuser

    @property
    def is_technician(self):
        return self.role == UserRole.TECHNICIAN

    @property
    def is_warehouse(self):
        return self.role == UserRole.WAREHOUSE
