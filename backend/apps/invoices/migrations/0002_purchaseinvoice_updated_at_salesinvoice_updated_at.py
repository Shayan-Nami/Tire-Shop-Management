from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseinvoice',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='تاریخ آخرین ویرایش'),
        ),
        migrations.AddField(
            model_name='salesinvoice',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='تاریخ آخرین ویرایش'),
        ),
    ]
