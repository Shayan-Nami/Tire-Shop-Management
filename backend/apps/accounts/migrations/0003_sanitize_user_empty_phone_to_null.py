from django.db import migrations


def sanitize_user_phone_to_null(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():
        if user.phone_number is not None and not str(user.phone_number).strip():
            user.phone_number = None
            user.save(update_fields=['phone_number'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_user_phone_number'),
    ]

    operations = [
        migrations.RunPython(sanitize_user_phone_to_null, reverse_code=noop_reverse),
    ]
