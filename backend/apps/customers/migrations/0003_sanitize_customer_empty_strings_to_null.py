from django.db import migrations


def sanitize_empty_strings_to_null(apps, schema_editor):
    Customer = apps.get_model('customers', 'Customer')
    for customer in Customer.objects.all():
        updated = False
        if customer.national_code is not None and not str(customer.national_code).strip():
            customer.national_code = None
            updated = True
        if customer.phone_number is not None and not str(customer.phone_number).strip():
            customer.phone_number = None
            updated = True
        if updated:
            customer.save(update_fields=['national_code', 'phone_number'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0002_customer_updated_at_alter_customer_national_code_and_more'),
    ]

    operations = [
        migrations.RunPython(sanitize_empty_strings_to_null, reverse_code=noop_reverse),
    ]
