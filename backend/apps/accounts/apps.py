from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'مدیریت کاربران و دسترسی‌ها'

    def ready(self):
        from config import checks  # noqa: F401  (registers deployment system checks)
