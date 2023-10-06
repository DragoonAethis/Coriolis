import os
from pathlib import Path

from django.apps import AppConfig
from django.conf import settings


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        from .signals.handlers import connect_signals

        super().ready()
        connect_signals()

        # Make sure all target media dirs are present when we need them:
        for path in ["ticketavatars", "templates", "previews"]:
            path = Path(os.path.join(settings.MEDIA_ROOT, path))
            path.mkdir(mode=0o755, parents=True, exist_ok=True)
