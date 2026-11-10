import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='تاریخ آخرین ویرایش'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='national_code',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True, validators=[django.core.validators.RegexValidator(message='کد ملی باید ۱۰ رقم عددی باشد.', regex='^\\d{10}$')], verbose_name='کد ملی'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='phone_number',
            field=models.CharField(max_length=20, unique=True, validators=[django.core.validators.RegexValidator(message='شماره موبایل باید با 09 شروع شده و ۱۱ رقم باشد.', regex='^09\\d{9}$')], verbose_name='شماره تماس'),
        ),
    ]
