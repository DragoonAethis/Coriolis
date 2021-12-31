import os
from pathlib import Path

from django.conf import settings
from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'

    def ready(self):
        super().ready()

        # Make sure all target media dirs are present when we need them:
        for path in ['ticketavatars', 'templates', 'previews']:
            path = Path(os.path.join(settings.MEDIA_ROOT, path))
            path.mkdir(mode=0o755, parents=True, exist_ok=True)
