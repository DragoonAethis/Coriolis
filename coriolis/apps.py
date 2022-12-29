from django.contrib.admin.apps import AdminConfig


class CoriolisAdminConfig(AdminConfig):
    default_site = "coriolis.admin.AdminSite"
