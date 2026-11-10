from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('supplier_id', models.AutoField(primary_key=True, serialize=False)),
                ('supplier_name', models.CharField(max_length=100, unique=True, verbose_name='نام شرکت یا شخص تأمین\u200cکننده')),
                ('phone_number', models.CharField(blank=True, max_length=20, null=True, verbose_name='شماره تلفن')),
                ('address', models.CharField(blank=True, max_length=200, null=True, verbose_name='نشانی')),
            ],
            options={
                'verbose_name': 'تأمین\u200cکننده',
                'verbose_name_plural': 'تأمین\u200cکنندگان',
                'db_table': 'Supplier',
            },
        ),
    ]
