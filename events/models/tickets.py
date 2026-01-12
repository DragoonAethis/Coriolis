import datetime
import decimal
import uuid

from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.mail import EmailMessage
from django.db import models
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from phonenumber_field.modelfields import PhoneNumberField

from events.models.events import Event, EventPage, EventPageType
from events.models.orgs import EventOrg
from events.models.users import User


class OnlinePaymentPolicy(models.IntegerChoices):
    DISABLED = 0, _("Disabled")
    ENABLED = 1, _("Enabled")
    REQUIRED = 2, _("Required")


class TicketFlag(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, verbose_name=_("event"))
    name = models.CharField(max_length=256, verbose_name=_("name"))
    description = models.TextField(
        blank=True,
        verbose_name=_("description"),
        help_text=_("What does this flag mean?"),
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("metadata"),
        help_text=_("Additional JSON metadata to attach to this flag."),
    )

    class Meta:
        verbose_name = _("ticket flag")
        verbose_name_plural = _("ticket flags")

    def __str__(self):
        return self.name


class TicketType(models.Model):
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
    flags = models.ManyToManyField(
        TicketFlag,
        blank=True,
        verbose_name=_("flags"),
        help_text=_("Flags to apply on all tickets of this type."),
    )
    upgrade_priority = models.PositiveIntegerField(
        default=0,
        verbose_name=_("upgrade priority"),
        help_text=_(
            "Tickets with lower priority may be upgraded to higher priority "
            "types in some situations (like being added to an organization)."
        ),
    )

    can_personalize = models.BooleanField(
        default=True,
        verbose_name=_("can personalize"),
        help_text=_("Determines if a ticket can be personalized at all."),
    )
    personalization_to = models.DateTimeField(
        verbose_name=_("personalization to"),
        help_text=_("Until when the ticket can be personalized?"),
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

    class Meta:
        verbose_name = _("ticket type")
        verbose_name_plural = _("ticket types")

    def __str__(self):
        return f"{self.name} ({self.event.name})"

    def __repr__(self):
        return f"{self.name} ({self.event.name}, {self.id})"

    def get_absolute_url(self):
        return reverse("registration_form", kwargs={"slug": self.event.slug, "id": self.id})

    def is_past_personalization_date(self):
        return datetime.datetime.now() > self.personalization_to


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


class TicketPaymentMethod(models.TextChoices):
    CASH = "cash", _("Cash")
    CARD = "card", _("Card")
    ONLINE = "online", _("Online")
    OTHER = "other", _("Other")


class TicketQuerySet(models.QuerySet):
    def valid_statuses_only(self):
        return self.filter(status__in=(TicketStatus.READY, TicketStatus.USED))

    def not_onsite(self):
        return self.filter(~Q(source=TicketSource.ONSITE))


class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"), null=True)
    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    type = models.ForeignKey(TicketType, on_delete=models.RESTRICT, verbose_name=_("type"))

    org = models.ForeignKey(
        EventOrg,
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
        verbose_name=_("org"),
        help_text=_("The organization this ticket belongs to."),
    )
    original_type = models.ForeignKey(
        TicketType,
        null=True,
        blank=True,
        default=None,
        related_name="+",
        on_delete=models.SET_NULL,
        verbose_name=_("original type"),
        help_text=_("The original ticket type, as it was set while joining the organization."),
    )

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
    flags = models.ManyToManyField(
        TicketFlag,
        blank=True,
        verbose_name=_("flags"),
        help_text=_("Flags specific to this ticket added on top of the type flags."),
    )

    source = models.CharField(
        max_length=16,
        verbose_name=_("source"),
        choices=TicketSource.choices,
        default=TicketSource.ADMIN,
    )
    payment_method = models.CharField(
        max_length=16,
        verbose_name=_("payment method"),
        choices=TicketPaymentMethod.choices,
        default='other',
    )

    name = models.CharField(max_length=256, blank=True, verbose_name=_("name"))
    email = models.EmailField(verbose_name=_("email"), blank=True)
    phone = PhoneNumberField(
        blank=True,
        verbose_name=_("phone"),
        help_text=_("Optional, used for notifications before/during the event"),
    )
    city = models.CharField(
        max_length=256,
        blank=True,
        verbose_name=_("city"),
        help_text=_("Optional city name for statistical purposes.")
    )
    age_gate = models.BooleanField(verbose_name=_("age gate"), help_text=_("Is the attendee of age?"))
    notes = models.TextField(
        blank=True,
        verbose_name=_("notes"),
        help_text=_("Public notes, visible to users/orgs, but not to accreditation."),
    )
    private_notes = models.TextField(
        blank=True,
        verbose_name=_("private notes"),
        help_text=_("Private org notes, visible only in the admin panel."),
    )

    # Accreditation process details
    accreditation_notes = models.TextField(
        blank=True,
        verbose_name=_("accreditation notes"),
        help_text=_("Notes shown during accreditation."),
    )
    issued_identifier = models.CharField(
        max_length=256,
        blank=True,
        verbose_name=_("issued identifier"),
    )
    stop_on_accreditation = models.BooleanField(
        default=False,
        verbose_name=_("stop on accreditation"),
        help_text=_(
            "Prevent the accreditation from letting this ticket through. "
            "Accreditation coordinator must manually handle the ticket."
        ),
    )

    # Customizations/Personalizations
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

    customization_approved_by = models.ForeignKey(
        User,
        related_name="approved_customized_ticket_set",
        on_delete=models.SET_NULL,
        verbose_name=_("personalization approved by"),
        help_text=_("The person who approved customizations on a ticket."),
        blank=True,
        null=True,
    )
    customization_approved_on = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        verbose_name=_("personalization approved on"),
        help_text=_("Date/time on which the ticket customizations were approved."),
    )

    # Non-database fields:
    _original_status: str | None = None

    objects = TicketQuerySet.as_manager()

    class Meta:
        verbose_name = _("ticket")
        verbose_name_plural = _("tickets")
        unique_together = ["event", "code"]
        indexes = [
            models.Index(fields=["event", "code"]),
            models.Index(fields=["event", "name"]),
            models.Index(fields=["event", "email"]),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def __str__(self):
        return f"{self.get_code()}: {self.name}"

    def __repr__(self):
        return f"{str(self)} ({self.id})"

    def save(self, *args, **kwargs):
        new_ticket = self.id is None
        super().save(*args, **kwargs)
        if new_ticket or self._original_status == self.status:
            return

        # Notify about the status change:
        if self.event.emails_enabled:
            EmailMessage(
                subject=_("%(event)s: Ticket '%(code)s' (new status)")
                % {"event": self.event.name, "code": self.get_code()},
                body=render_to_string(
                    "events/emails/ticket_changed.html",
                    {
                        "event": self.event,
                        "ticket": self,
                    },
                ).strip(),
                to=[self.email],
                reply_to=[self.event.org_mail],
            ).send()

    def get_absolute_url(self):
        return reverse("ticket_details", kwargs={"slug": self.event.slug, "ticket_id": self.id})

    def get_flags(self) -> set[TicketFlag]:
        return set(self.type.flags.all()) | set(self.flags.all())

    def get_preview_url(self) -> str | None:
        url = None

        if self.preview:
            url = self.preview.url
        elif self.image:
            url = self.image.url

        if url:  # Poor Man's ETag:
            url += f"?updated={self.updated.timestamp():.0f}"

        return url

    def get_status_deadline_display(self):
        if self.status_deadline > datetime.datetime.now():
            timestamp = naturaltime(self.status_deadline)
        else:
            timestamp = _("soon")

        if self.status == TicketStatus.WAITING_FOR_PAYMENT:
            template = _("if unpaid, ticket will be cancelled %(timestamp)s")
        else:
            template = _("status will change %(timestamp)s")

        return template % {"timestamp": timestamp}

    def get_status_css_class(self):
        status_to_class: dict[str, str] = {
            TicketStatus.CANCELLED: "danger",
            TicketStatus.WAITING: "warning",
            TicketStatus.WAITING_FOR_PAYMENT: "warning",
            TicketStatus.READY: "success",
            TicketStatus.USED: "secondary",
        }

        return status_to_class.get(self.status) or "info"

    def get_status_icon(self):
        status_to_icon: dict[str, str] = {
            TicketStatus.CANCELLED: "x-circle",
            TicketStatus.WAITING: "clock",
            TicketStatus.WAITING_FOR_PAYMENT: "credit-card",
            TicketStatus.READY: "check-circle",
            TicketStatus.USED: "check-all",
        }

        return status_to_icon.get(self.status) or "question"

    def get_price(self):
        if self.override_price:
            return self.price

        return self.type.price

    def is_paid_for(self):
        return self.paid or self.get_price().amount == decimal.Decimal(0)

    def is_cancelled(self) -> bool:
        return self.status == TicketStatus.CANCELLED

    def is_waiting_for_payment(self) -> bool:
        return self.status == TicketStatus.WAITING_FOR_PAYMENT

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

    def status_allows_personalization(self) -> bool:
        return self.status in (
            TicketStatus.READY,
            TicketStatus.WAITING_FOR_PAYMENT,
            TicketStatus.WAITING,
        )

    def can_personalize(self) -> bool:
        return (
            self.status_allows_personalization()
            and self.type.can_personalize
            and not self.type.is_past_personalization_date()
        )

    def get_code(self) -> str:
        prefix = self.type.code_prefix if self.type is not None else ""
        code = str(self.code)
        return prefix + ("0" * (self.event.ticket_code_length - len(code))) + code
