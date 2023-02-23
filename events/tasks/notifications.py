import logging
from typing import Optional
from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

import requests
import dramatiq

from events.models import Event, Ticket, NotificationChannel
from events.models.notifications import NotificationChannelSource, NotificationChannelTarget, NotificationChannelPayload

TELEGRAM_BOT_ENDPOINT = "https://api.telegram.org/bot{token}/{method}"


@dataclass
class NotificationChannelTicketUsedPayload(NotificationChannelPayload):
    """Used to notify that a pre-purchased ticket has been used at the entry gate."""
    ticket_id: str

    def get_ticket(self):
        try:
            return Ticket.objects.get(id=self.ticket_id)
        except Ticket.DoesNotExist:
            logging.error(f"Tried to notify about missing ticket: {self.ticket_id}")
            return None

    def get_markdown_text(self, bold_marker: str):
        if not (ticket := self.get_ticket()):
            return None

        parts = [
            f"{bold_marker}{ticket.get_code()}{bold_marker}",
            f"{_('☑️ Paid') if ticket.paid else str(ticket.get_price())}",
            f"{ticket.type.name}",
            f"{_('Source')}: {ticket.get_source_display()}",
        ]

        return " \- ".join([str(x) for x in parts])

    def get_discord_text(self) -> Optional[str]:
        return self.get_markdown_text("**")

    def get_telegram_text(self) -> Optional[str]:
        return self.get_markdown_text("*")


@dramatiq.actor
def notify_channel(event_id: int, source: NotificationChannelSource, payload_args: dict):
    payload: NotificationChannelPayload
    if source == NotificationChannelSource.TICKET_USED:
        payload = NotificationChannelTicketUsedPayload(**payload_args)
    else:
        logging.error(f"Unknown notification source: {source}")
        return

    channels = NotificationChannel.objects.filter(event_id=event_id, source=source)
    for channel in channels:
        if not channel.enabled:
            continue

        if channel.target == NotificationChannelTarget.DISCORD_WEBHOOK:
            if not (content := payload.get_discord_text()):
                logging.warning(f'Tried to notify Discord with a payload that does not return Markdown: {payload=}')
                continue

            discord_webhook_url = channel.configuration.get('url')
            if discord_webhook_url is None:
                logging.warning(f'Tried to notify Discord without a webhook URL on channel: {channel=}')
                continue

            r = requests.post(discord_webhook_url, json={'content': content})
            if not r.ok:
                logging.warning(f"Discord request returned {r.status_code}: {r.text}")

        elif channel.target == NotificationChannelTarget.TELEGRAM_MESSAGE:
            if not (content := payload.get_telegram_text()):
                logging.warning(f'Tried to notify Telegram with a payload that does not return Markdown: {payload=}')
                continue

            token = channel.configuration.get('token')
            chat_id = channel.configuration.get('chat_id')
            if not token or not chat_id:
                logging.warning(f"Tried to notify Telegram with invalid configuration (missing token or chat_id).")
                continue

            url = TELEGRAM_BOT_ENDPOINT.format(token=token, method="sendMessage")
            r = requests.post(url, json={
                "chat_id": chat_id,
                "text": content,
                "parse_mode": "MarkdownV2",
                "disable_notification": True,
            })
            
            if not r.ok:
                logging.warning(f"Telegram request returned {r.status_code}: {r.text}")

        else:
            logging.error(f'Unknown notification target on channel: {channel=}')
