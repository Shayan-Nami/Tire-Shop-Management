import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0008_alter_stockmovement_purchase_invoice_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StockProjectionRepair',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stock_before', models.PositiveIntegerField()),
                ('stock_after', models.PositiveIntegerField()),
                ('reason', models.TextField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('last_movement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='projection_repairs', to='catalog.stockmovement')),
                ('tire', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='projection_repairs', to='catalog.tire')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_projection_repairs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-pk'],
            },
        ),
    ]
