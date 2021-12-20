from django.conf import settings
from events.models import EventPage


def global_listed_event_pages(request):
    """Add globally-available and shown event pages to the template context,
    so that each template can add those into the event page menu."""
    return {
        'global_event_pages': EventPage.objects.filter(event=None, hidden=False)
    }
