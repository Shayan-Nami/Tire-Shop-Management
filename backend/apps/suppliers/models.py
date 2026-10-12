from django.db import models

class Supplier(models.Model):
    supplier_id = models.AutoField(primary_key=True)
    supplier_name = models.CharField(max_length=100, unique=True, verbose_name='نام شرکت یا شخص تأمین‌کننده')
    phone_number = models.CharField(max_length=20, null=True, blank=True, verbose_name='شماره تلفن')
    address = models.CharField(max_length=200, null=True, blank=True, verbose_name='نشانی')

    class Meta:
        db_table = 'Supplier'
        verbose_name = 'تأمین‌کننده'
        verbose_name_plural = 'تأمین‌کنندگان'

    def __str__(self):
        return self.supplier_name
