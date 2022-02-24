import logging
from typing import Optional
from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

import requests
import dramatiq

from events.models import Event, Ticket, NotificationChannel
from events.models.notifications import NotificationChannelSource, NotificationChannelTarget, NotificationChannelPayload


@dataclass
class NotificationChannelTicketUsedPayload(NotificationChannelPayload):
    """Used to notify that a pre-purchased ticket has been used at the entry gate."""
    ticket_id: str

    def get_markdown(self) -> Optional[str]:
        try:
            ticket = Ticket.objects.get(id=self.ticket_id)
        except Ticket.DoesNotExist:
            logging.error(f"Tried to notify about missing ticket: {self.ticket_id}")
            return None

        parts = [
            f"**{ticket.get_code()}**",
            _('☑️ Paid') if ticket.paid else str(ticket.type.price),
            ticket.get_source_display(),
            ticket.type.name
        ]

        return " - ".join(parts)


@dramatiq.actor
def notify_channel(event_id: Event, source: NotificationChannelSource, payload_args: dict):
    payload: NotificationChannelPayload
    if source == NotificationChannelSource.TICKET_USED:
        payload = NotificationChannelTicketUsedPayload(**payload_args)
    else:
        logging.error(f"Unknown notification source: {source}")
        return

    channels = NotificationChannel.objects.filter(event_id=event_id, source=source)
    for channel in channels:
        if channel.target == NotificationChannelTarget.DISCORD_WEBHOOK:
            content = payload.get_markdown()
            if content is None:
                logging.warning(f'Tried to notify Discord with a payload that does not return Markdown: {payload=}')
                continue

            discord_webhook_url = channel.configuration.get('url')
            if discord_webhook_url is None:
                logging.warning(f'Tried to notify Discord without a webhook URL on channel: {channel=}')

            requests.post(discord_webhook_url, json={'content': content})
        else:
            logging.error(f'Unknown notification target on channel: {channel=}')
