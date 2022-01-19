from django.conf import settings
from allauth_2fa.middleware import BaseRequire2FAMiddleware


class RequireSuperuser2FAMiddleware(BaseRequire2FAMiddleware):
    def require_2fa(self, request):
        return (
            (request.user.is_superuser or request.user.is_staff)
            and not settings.DEBUG
        )


class ForceDefaultLanguageMiddleware:
    """
    If registered before LocaleMiddleware, this middleware removes the Accept-Language header
    from the request, essentially always falling back to settings.LANGUAGE_CODE as the default
    language, if not set manually by the user. Source: https://djangosnippets.org/snippets/218/
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.META.pop('HTTP_ACCEPT_LANGUAGE', None)
        return self.get_response(request)
