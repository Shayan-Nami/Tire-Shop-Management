import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0004_paymentvoucher_cancellation_reason_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='customerrefundvoucher',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_customer_refunds', to=settings.AUTH_USER_MODEL, verbose_name='کاربر صادرکننده'),
        ),
        migrations.AddField(
            model_name='paymentvoucher',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_payment_vouchers', to=settings.AUTH_USER_MODEL, verbose_name='کاربر صادرکننده'),
        ),
        migrations.AddField(
            model_name='receiptvoucher',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_receipt_vouchers', to=settings.AUTH_USER_MODEL, verbose_name='کاربر صادرکننده'),
        ),
    ]
