from django.conf import settings
from events.models import EventPage


def global_listed_event_pages(request):
    """Add globally-available and shown event pages to the template context,
    so that each template can add those into the event page menu."""
    return {
        'login_notice': settings.LOGIN_NOTICE,
        'login_footer': settings.LOGIN_FOOTER,
        'cookies_link': settings.COOKIES_POLICY_LINK,
        'global_event_pages': EventPage.objects.filter(event=None, hidden=False)
    }
