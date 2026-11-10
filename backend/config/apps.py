from django.contrib.admin.apps import AdminConfig


class ThrottledAdminConfig(AdminConfig):
    default_site = 'config.admin_site.ThrottledAdminSite'
