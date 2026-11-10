import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_sanitize_user_empty_phone_to_null'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True, validators=[django.core.validators.RegexValidator(message='شماره موبایل باید با 09 شروع شده و ۱۱ رقم باشد.', regex='^09\\d{9}$')], verbose_name='شماره موبایل'),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(condition=models.Q(('phone_number__isnull', False), models.Q(('phone_number', ''), _negated=True)), fields=('phone_number',), name='unique_user_phone_number_not_null'),
        ),
    ]
