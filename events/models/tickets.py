import datetime
import uuid
from typing import Optional

from colorfield.fields import ColorField
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from phonenumber_field.modelfields import PhoneNumberField

from events.models.events import Event, EventPage, EventPageType
from events.models.users import User


class OnlinePaymentPolicy(models.IntegerChoices):
    DISABLED = 0, _("Disabled")
    ENABLED = 1, _("Enabled")
    REQUIRED = 2, _("Required")


class TicketType(models.Model):
    class Meta:
        verbose_name = _("ticket type")
        verbose_name_plural = _("ticket types")

    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    name = models.CharField(max_length=256, verbose_name=_("name"))
    description = models.TextField(
        verbose_name=_("description"),
        help_text=_("Shown in the ticket choice screen. Supports Markdown."),
    )
    long_description = models.TextField(
        verbose_name=_("long description"),
        help_text=_("Shown on the ticket purchase form. Supports Markdown."),
    )
    code_prefix = models.CharField(
        max_length=8,
        blank=True,
        verbose_name=_("code prefix"),
        help_text=_("Characters in front of all the ticket codes of this type."),
    )
    price = MoneyField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("price"),
        default=Money(0, settings.CURRENCY),
        default_currency=settings.CURRENCY,
    )
    color = ColorField(
        default="#FF0000",
        verbose_name=_("color"),
        help_text=_("Extra color shown on the ticket choice screen."),
    )
    short_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name=_("short name"),
        help_text=_("Usually used for ticket rendering."),
    )

    can_personalize = models.BooleanField(
        default=True,
        verbose_name=_("can personalize"),
        help_text=_("Determines if a ticket can be personalized at all."),
    )
    can_specify_shirt_size = models.BooleanField(
        default=False,
        verbose_name=_("can specify shirt size"),
        help_text=_("Determines if a shirt size can be personalized."),
    )

    registration_from = models.DateTimeField(verbose_name=_("registration from"))
    registration_to = models.DateTimeField(verbose_name=_("registration to"))
    self_registration = models.BooleanField(
        default=True,
        verbose_name=_("self-registration"),
        help_text=_("Determines if the ticket can be purchased online."),
    )

    on_site_registration = models.BooleanField(
        default=True,
        verbose_name=_("on-site registration"),
        help_text=_("Determines if the ticket can be purchased on-site."),
    )
    online_payment_policy = models.IntegerField(
        verbose_name=_("online payment policy"),
        choices=OnlinePaymentPolicy.choices,
        default=OnlinePaymentPolicy.ENABLED,
    )
    online_payment_window = models.PositiveIntegerField(
        default=0,
        verbose_name=_("online payment window"),
        help_text=_(
            "If online payment is required, how many minutes "
            "should we wait for a valid payment? A ticket is "
            "cancelled automatically when time's up. Setting "
            "this to zero disables automatic cancellation."
        ),
    )
    display_order = models.IntegerField(
        default=0,
        verbose_name=_("display order"),
        help_text=_("Order in which ticket types are displayed (0, 1, 2, ...)."),
    )

    special_payment_page = models.ForeignKey(
        EventPage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("special payment page"),
        help_text=_(
            "If you want to use special payment instructions for this "
            "ticket type, create an Event Page with those, set its type "
            "to Ticket Payment Instructions and select it here."
        ),
        limit_choices_to={"page_type": EventPageType.TICKET_PAYMENT_INFO},
    )

    purchase_rate_limit_secs = models.PositiveIntegerField(
        default=0,
        verbose_name=_("purchase rate limit seconds"),
        help_text=_(
            "Determines if users have to wait between purchases of this "
            "ticket type. Useful for sale fairness of high-demand tickets. "
            "Set to 0 to disable this feature, or the number of seconds to "
            "make users wait after purchasing."
        ),
    )

    max_tickets = models.PositiveSmallIntegerField(verbose_name=_("max tickets"))
    tickets_remaining = models.PositiveSmallIntegerField(verbose_name=_("tickets remaining"))
    show_tickets_remaining = models.BooleanField(
        default=True,
        verbose_name=_("show tickets remaining"),
        help_text=_("Display the number of tickets left publicly?"),
    )

    def __str__(self):
        return f"{self.name} ({self.event.name})"

    def __repr__(self):
        return f"{self.name} ({self.event.name}, {self.id})"

    def get_absolute_url(self):
        return reverse("registration_form", kwargs={"slug": self.event.slug, "id": self.id})

    def can_register_or_change(self):
        return datetime.datetime.now() < self.registration_to


class TicketStatus(models.TextChoices):
    CANCELLED = "CNCL", _("Cancelled")
    WAITING = "WAIT", _("Waiting for Organizers")
    WAITING_FOR_PAYMENT = "WPAY", _("Waiting for online payment")
    READY = "OKNP", _("Ready")
    USED = "USED", _("Used")


class TicketSource(models.TextChoices):
    ADMIN = "admin", _("Administrative")
    ONLINE = "online", _("Online")
    ONSITE = "onsite", _("On-site")


class Ticket(models.Model):
    class Meta:
        verbose_name = _("ticket")
        verbose_name_plural = _("tickets")
        unique_together = ["event", "code"]
        indexes = [
            models.Index(fields=["event", "code"]),
            models.Index(fields=["event", "name"]),
            models.Index(fields=["event", "email"]),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"), null=True)
    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    type = models.ForeignKey(TicketType, on_delete=models.RESTRICT, verbose_name=_("type"))

    paid = models.BooleanField(verbose_name=_("paid"), default=False)
    contributed_value = MoneyField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("contributed value"),
        help_text=_("Collected ticket value to count in the exported metrics."),
        default=Money(0, settings.CURRENCY),
        default_currency=settings.CURRENCY,
    )

    override_price = models.BooleanField(
        verbose_name=_("override price"),
        default=False,
        help_text=_("Ignore the ticket type price and use the value set here."),
    )
    price = MoneyField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("price"),
        default=Money(0, settings.CURRENCY),
        default_currency=settings.CURRENCY,
    )

    status = models.CharField(
        max_length=4,
        verbose_name=_("status"),
        choices=TicketStatus.choices,
        default=TicketStatus.WAITING,
    )
    status_deadline = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        verbose_name=_("status deadline"),
        help_text=_(
            "Date/time until which the current status is valid. The system "
            "will automatically update the ticket after this date as needed."
        ),
    )

    source = models.CharField(
        max_length=16,
        verbose_name=_("source"),
        choices=TicketSource.choices,
        default=TicketSource.ADMIN,
    )

    name = models.CharField(max_length=256, blank=True, verbose_name=_("name"))
    email = models.EmailField(verbose_name=_("email"), blank=True)
    phone = PhoneNumberField(
        blank=True,
        verbose_name=_("phone"),
        help_text=_("Optional, used for notifications before/during the event"),
    )
    age_gate = models.BooleanField(verbose_name=_("age gate"), help_text=_("Is the attendee of age?"))
    notes = models.TextField(
        blank=True,
        verbose_name=_("notes"),
        help_text=_("Public notes, visible to users/orgs"),
    )
    private_notes = models.TextField(
        blank=True,
        verbose_name=_("private notes"),
        help_text=_("Private org notes, visible only in the admin panel"),
    )

    code = models.PositiveIntegerField(
        verbose_name=_("code"),
        help_text=_("Code printed on the ticket. Required for pickup on site."),
    )
    nickname = models.CharField(
        max_length=256,
        blank=True,
        verbose_name=_("nickname"),
        help_text=_("Printed on the customized ticket"),
    )
    shirt_size = models.CharField(
        max_length=4,
        blank=True,
        verbose_name=_("shirt size"),
        help_text=_("Shirt size chosen by the attendee."),
    )
    image = models.ImageField(
        blank=True,
        verbose_name=_("image"),
        help_text=_("Printed on the customized ticket."),
    )
    preview = models.ImageField(
        blank=True,
        verbose_name=_("preview"),
        help_text=_("Automatically generated preview image."),
    )

    # Non-database fields:
    _original_status: Optional[str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def __str__(self):
        return f"{self.get_code()}: {self.name}"

    def __repr__(self):
        return f"{str(self)} ({self.id})"

    def get_absolute_url(self):
        return reverse("ticket_details", kwargs={"slug": self.event.slug, "ticket_id": self.id})

    def get_price(self):
        if self.override_price:
            return self.price

        return self.type.price

    def is_cancelled(self) -> bool:
        return self.status == TicketStatus.CANCELLED

    def can_cancel(self) -> bool:
        return not self.paid and self.status in (
            TicketStatus.READY,
            TicketStatus.WAITING_FOR_PAYMENT,
        )

    def can_pay_online(self) -> bool:
        return (
            datetime.datetime.now() < self.event.date_to
            and not self.paid
            and self.status in (TicketStatus.READY, TicketStatus.WAITING_FOR_PAYMENT)
            and self.event.payment_enabled
            and self.type.online_payment_policy != OnlinePaymentPolicy.DISABLED
        )

    def can_personalize(self) -> bool:
        return (
            self.status
            in (
                TicketStatus.READY,
                TicketStatus.WAITING_FOR_PAYMENT,
                TicketStatus.WAITING,
            )
            and self.type.can_register_or_change()
            and self.type.can_personalize
        )

    def get_code(self) -> str:
        prefix = self.type.code_prefix if self.type is not None else ""
        code = str(self.code)
        return prefix + ("0" * (self.event.ticket_code_length - len(code))) + code

    def save(self, *args, **kwargs):
        new_ticket = self.id is None
        super().save(*args, **kwargs)
        if new_ticket or self._original_status == self.status:
            return

        # Notify about the status change:
        if self.event.emails_enabled:
            EmailMessage(
                _("%(event)s: Ticket '%(code)s' (new status)") % {"event": self.event.name, "code": self.get_code()},
                render_to_string(
                    "events/emails/ticket_changed.html",
                    {
                        "event": self.event,
                        "ticket": self,
                    },
                ).strip(),
                settings.SERVER_EMAIL,
                [self.email],
                reply_to=[self.event.org_mail],
            ).send()

    @staticmethod
    def by_event_user(event: Event, user: User):
        return Ticket.objects.filter(event=event, user=user)
