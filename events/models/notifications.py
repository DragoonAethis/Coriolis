from abc import ABC
from typing import Optional

from django.db import models
from django.utils.translation import gettext_lazy as _

from events.models.events import Event


class NotificationChannelPayload(ABC):
    """Stores a payload and provides data rendering methods for various
    notification channel sources. This class must be overridden per source."""

    def get_discord_text(self) -> Optional[str]:
        return None

    def get_telegram_text(self) -> Optional[str]:
        return None


class NotificationChannelSource(models.TextChoices):
    TICKET_USED = 'ticket-used', _("Ticket Used")


class NotificationChannelTarget(models.TextChoices):
    DISCORD_WEBHOOK = 'discord-webhook', _("Discord Webhook")
    TELEGRAM_MESSAGE = 'telegram-message', _("Telegram Message")


class NotificationChannel(models.Model):
    class Meta:
        verbose_name = _("notification channel")
        verbose_name_plural = _("notification channels")

    event = models.ForeignKey(Event, on_delete=models.CASCADE, verbose_name=_("event"))
    name = models.CharField(max_length=256, verbose_name=_("name"),
                            help_text=_("A custom label for this channel - not used anywhere."))
    enabled = models.BooleanField(default=True, verbose_name=_("enabled"),
                                  help_text=_("Enable or disable this channel."))
    source = models.CharField(max_length=32, verbose_name=_("source"),
                              choices=NotificationChannelSource.choices,
                              help_text=_("Which events to send to this channel?"))
    target = models.CharField(max_length=16, verbose_name=_("target"),
                              choices=NotificationChannelTarget.choices,
                              help_text=_("Where to send events from this channel?"))
    configuration = models.JSONField(verbose_name=_("configuration"),
                                     help_text=_("Channel target configuration, in JSON. See docs: "
                                                 "https://github.com/DragoonAethis/Coriolis/wiki/Notification-Channels"))  # noqa
