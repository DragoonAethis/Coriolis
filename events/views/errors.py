from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _


def error_handler(request, message):
    messages.error(request, message)
    return redirect("index")


def error_400(request, exception=None):  # Bad Request
    return error_handler(request, _("You don't have permissions to access this page."))


def error_403(request, exception=None):  # Forbidden
    return error_handler(request, _("You don't have permissions to access this page."))


def error_404(request, exception=None):  # Not Found
    return error_handler(request, _("The page you tried to visit was not found."))


def error_500(request, exception=None):  # Server Error
    return error_handler(request, _("The server encountered an unknown error."))
