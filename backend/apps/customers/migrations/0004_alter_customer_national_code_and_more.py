import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0003_sanitize_customer_empty_strings_to_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='national_code',
            field=models.CharField(blank=True, max_length=10, null=True, validators=[django.core.validators.RegexValidator(message='کد ملی باید ۱۰ رقم عددی باشد.', regex='^\\d{10}$')], verbose_name='کد ملی'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True, validators=[django.core.validators.RegexValidator(message='شماره موبایل باید با 09 شروع شده و ۱۱ رقم باشد.', regex='^09\\d{9}$')], verbose_name='شماره تماس'),
        ),
        migrations.AddConstraint(
            model_name='customer',
            constraint=models.UniqueConstraint(condition=models.Q(('phone_number__isnull', False), models.Q(('phone_number', ''), _negated=True)), fields=('phone_number',), name='unique_customer_phone_number_not_null'),
        ),
        migrations.AddConstraint(
            model_name='customer',
            constraint=models.UniqueConstraint(condition=models.Q(('national_code__isnull', False), models.Q(('national_code', ''), _negated=True)), fields=('national_code',), name='unique_customer_national_code_not_null'),
        ),
    ]
