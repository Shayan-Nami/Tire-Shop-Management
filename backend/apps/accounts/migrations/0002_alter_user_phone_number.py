import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True, validators=[django.core.validators.RegexValidator(message='شماره موبایل باید با 09 شروع شده و ۱۱ رقم باشد.', regex='^09\\d{9}$')], verbose_name='شماره موبایل'),
        ),
    ]
