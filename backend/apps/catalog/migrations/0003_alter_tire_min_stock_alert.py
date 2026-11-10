from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_alter_tire_stock_quantity_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tire',
            name='min_stock_alert',
            field=models.PositiveIntegerField(default=5, verbose_name='حداقل موجودی جهت هشدار'),
        ),
    ]
