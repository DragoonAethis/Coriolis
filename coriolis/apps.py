from django.contrib.admin.apps import AdminConfig


class CoriolisAdminConfig(AdminConfig):
    default_site = "events.admin.site.AdminSite"
