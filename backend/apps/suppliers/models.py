from django.db import models

from utils.persian import normalize_optional_digits, supplier_phone_validator


class Supplier(models.Model):
    supplier_id = models.AutoField(primary_key=True)
    supplier_name = models.CharField(max_length=100, unique=True, verbose_name='نام شرکت یا شخص تأمین‌کننده')
    phone_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        validators=[supplier_phone_validator],
        verbose_name='شماره تلفن',
    )
    address = models.CharField(max_length=200, null=True, blank=True, verbose_name='نشانی')

    class Meta:
        db_table = 'Supplier'
        verbose_name = 'تأمین‌کننده'
        verbose_name_plural = 'تأمین‌کنندگان'

    def clean_fields(self, exclude=None):
        self.phone_number = normalize_optional_digits(self.phone_number)
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        self.phone_number = normalize_optional_digits(self.phone_number)

    def save(self, *args, **kwargs):
        self.phone_number = normalize_optional_digits(self.phone_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.supplier_name
