import uuid
import datetime
from typing import Iterable, Optional

from django.db import models
from django.conf import settings
from django.shortcuts import reverse
from django.core.mail import EmailMessage
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from phonenumber_field.modelfields import PhoneNumberField
from djmoney.models.fields import MoneyField
from colorfield.fields import ColorField
from payments.models import BasePayment
from payments import PurchasedItem

from .utils import get_ticket_preview_path


class User(AbstractUser):
    def __str__(self):
        return f"{self.email or self.username or self.id}"


class Event(models.Model):
    class Meta:
        verbose_name = _("event")
        verbose_name_plural = _("events")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=256, verbose_name=_("name"),
                            help_text=_("Human-readable name for the event."))
    slug = models.CharField(max_length=64, verbose_name=_("slug"),
                            help_text=_("Short name used in links."))
    location = models.CharField(max_length=256, verbose_name=_("location"),
                                help_text=_("Physical place where the event will take place."))
    location_link = models.CharField(max_length=256, verbose_name=_("location link"),
                                     help_text=_("Link to Google Maps or OSM."))
    website_link = models.CharField(max_length=256, verbose_name=_("website link"),
                                    help_text=_("Link to the main event website."))
    contact_link = models.CharField(max_length=256, verbose_name=_("contact link"),
                                    help_text=_("Used for the big Contact Organizers button."))
    org_mail = models.CharField(max_length=256, verbose_name=_("org mail"),
                                help_text=_("Used as the Reply To address for e-mail notifications."))

    date_from = models.DateTimeField(verbose_name=_("date from"))
    date_to = models.DateTimeField(verbose_name=_("date to"))
    active = models.BooleanField(default=True, verbose_name=_("active"))
    payment_enabled = models.BooleanField(default=True, verbose_name=_("payment enabled"),
                                          help_text=_("Enable or disable "))
    notice = models.TextField(blank=True, verbose_name=_("notice"),
                              help_text=_("Notice to be shown below the event description, if set."))

    description = models.TextField(verbose_name=_("description"),
                                   help_text=_("Text shown on the main page. Supports Markdown."))
    footer_content = models.TextField(verbose_name=_("footer content"),
                                      help_text=_("Muted text shown in the footer. Supports Markdown."))

    ticket_code_length = models.PositiveSmallIntegerField(verbose_name=_("ticket code length"),
                                                          validators=[
                                                              MinValueValidator(3),
                                                              MaxValueValidator(32)
                                                          ])

    def __str__(self):
        return self.name


class EventPage(models.Model):
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'slug'], name='event_pages_with_unique_slugs')]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("event"),
                              help_text=_("If not set, will be shown for all events."))
    name = models.CharField(max_length=256, verbose_name=_("name"))
    slug = models.CharField(max_length=64, verbose_name=_("slug"),
                            help_text=_("Short name used in links. Event-specific pages have precedence."))
    hidden = models.BooleanField(default=False, verbose_name=_("hidden"),
                                 help_text=_("Whenever to hide this page in the page listing."))
    content = models.TextField(verbose_name=_("content"),
                               help_text=_("Page content. Supports markdown."))

    def __str__(self):
        if self.event is not None:
            return f"{self.name} ({self.event.name})"
        else:
            return self.name


class TicketType(models.Model):
    class Meta:
        verbose_name = _("ticket type")
        verbose_name_plural = _("ticket types")

    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    name = models.CharField(max_length=256, verbose_name=_("name"))
    description = models.TextField(verbose_name=_("description"),
                                   help_text=_("Shown in the ticket choice screen. Supports Markdown."))
    long_description = models.TextField(verbose_name=_("long description"),
                                        help_text=_("Shown on the ticket purchase form. Supports Markdown."))
    code_prefix = models.CharField(max_length=8, blank=True, verbose_name=_("code prefix"),
                                   help_text=_("Characters in front of all the ticket codes of this type."))
    price = MoneyField(max_digits=10, decimal_places=2, default_currency=settings.CURRENCY, verbose_name=_("price"))
    color = ColorField(default='#FF0000', verbose_name=_("color"),
                       help_text=_("Extra color shown on the ticket choice screen."))

    preview_image = models.ImageField(blank=True, verbose_name=_("preview image"), upload_to=get_ticket_preview_path,
                                      help_text=_("Used for generating ticket previews."))
    preview_box_coords = models.CharField(max_length=32, blank=True, verbose_name=_("preview box coords"),
                                          help_text=_("Box coords for the ticket preview generator. Docs: ") +
                                                    "https://github.com/DragoonAethis/Coriolis/wiki/Ticket-Preview-Generator",
                                          validators=[])  # noqa

    registration_from = models.DateTimeField(verbose_name=_("registration from"))
    registration_to = models.DateTimeField(verbose_name=_("registration to"))
    self_registration = models.BooleanField(default=True, verbose_name=_("self-registration"),
                                            help_text=_("Determines if the ticket can be purchased online."))
    must_pay_online = models.BooleanField(default=False, verbose_name=_("must pay online"),
                                          help_text=_("Determines if the ticket can be paid on-site or online only."))
    display_order = models.IntegerField(default=0, verbose_name=_("display order"),
                                        help_text=_("Order in which ticket types are displayed (0, 1, 2, ...)."))

    max_tickets = models.PositiveSmallIntegerField(verbose_name=_("max tickets"))
    tickets_remaining = models.PositiveSmallIntegerField(verbose_name=_("tickets remaining"))
    show_tickets_remaining = models.BooleanField(default=True, verbose_name=_("show tickets remaining"),
                                                 help_text=_("Display the number of tickets left publicly?"))

    def __str__(self):
        return f"{self.name} ({self.id})"

    def clean(self):
        super().clean()

        if self.preview_image is not None:
            try:
                self.get_preview_box_coords(fallback=False)
            except ValueError as ex:
                raise ValidationError(ex)

    def can_register_or_change(self):
        return datetime.datetime.now() < self.registration_to

    def get_preview_box_coords(self, fallback=True) -> tuple[int, int, int, int]:
        if self.preview_image is None:
            return 0, 0, 0, 0  # Just don't bother.

        width, height = self.preview_image.width, self.preview_image.height
        default_box_coords = (0, 0, self.preview_image.width, self.preview_image.height)

        if self.preview_box_coords is None or len(self.preview_box_coords.strip()) == 0:
            return default_box_coords

        try:
            parts = [int(part) for part in self.preview_box_coords.split(" ")]
            if len(parts) != 4:
                raise ValueError("Invalid number of parts.")

            if any([x < 0 for x in parts]):
                raise ValueError("All numbers in box coords must be >= 0.")

            bx, by, bw, bh = parts
            if bx not in range(0, width) or by not in range(0, height):
                raise ValueError(f"Box start ({bx}, {by}) not within range (0..{width}, 0..{height}).")

            ex, ey = bx + bw, by + bh
            if ex not in range(0, width + 1) or ey not in range(0, height + 1):
                raise ValueError(f"Box end ({ex}, {ey}) not within range (0..{width}, 0..{height}).")

            return bx, by, bw, bh  # All good!
        except ValueError:
            if fallback:
                return default_box_coords
            else:
                raise


class Ticket(models.Model):
    class Meta:
        verbose_name = _("ticket")
        verbose_name_plural = _("tickets")
        unique_together = ['event', 'code']
        indexes = [
            models.Index(fields=['event', 'code']),
            models.Index(fields=['event', 'name']),
            models.Index(fields=['event', 'email']),
        ]

    class TicketStatus(models.TextChoices):
        CANCELLED = 'CNCL', _("Cancelled")
        WAITING = 'WAIT', _("Waiting for Organizers")
        WAITING_FOR_PAYMENT = 'WPAY', _("Waiting for online payment")
        READY_PAY_ON_SITE = 'OKNP', _("Ready (payment on site)")
        READY_PAID = 'OKPD', _("Ready (paid)")
        USED = 'USED', _("Used")
        USED_ON_SITE = 'ONST', _("Used on site")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"), null=True)
    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    type = models.ForeignKey(TicketType, on_delete=models.RESTRICT, verbose_name=_("type"))
    status = models.CharField(max_length=4, verbose_name=_("status"),
                              choices=TicketStatus.choices, default=TicketStatus.WAITING)

    name = models.CharField(max_length=256, blank=True, verbose_name=_("name"))
    email = models.EmailField(verbose_name=_("email"), blank=True)
    phone = PhoneNumberField(blank=True, verbose_name=_("phone"),
                             help_text=_("Optional, used for notifications before/during the event"))
    age_gate = models.BooleanField(verbose_name=_("age gate"),
                                   help_text=_("Is the attendee of age?"))
    notes = models.TextField(blank=True, verbose_name=_("notes"),
                             help_text=_("Optional, notes for organizers"))

    code = models.PositiveIntegerField(verbose_name=_("code"),
                                       help_text=_("Code printed on the ticket. Required for pickup on site."))
    nickname = models.CharField(max_length=256, blank=True, verbose_name=_("nickname"),
                                help_text=_("Printed on the customized ticket"))
    image = models.ImageField(blank=True, verbose_name=_("image"),
                              help_text=_("Printed on the customized ticket."))
    preview = models.ImageField(blank=True, verbose_name=_("preview"),
                                help_text=_("Automatically generated preview image."))

    # Non-database fields:
    _original_status: Optional[str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def __str__(self):
        return f"{self.code}: {self.name} ({self.id})"

    def is_cancelled(self) -> bool:
        return self.status == Ticket.TicketStatus.CANCELLED

    def can_cancel(self) -> bool:
        return self.status in ('OKNP', 'WPAY')

    def can_pay_online(self) -> bool:
        return (
            self.status in ('OKNP', 'WPAY')
            and self.event.payment_enabled
            and datetime.datetime.now() < self.event.date_to
        )

    def can_personalize(self):
        return (
            self.status in ('OKNP', 'WPAY', 'OKPD')
            and self.type.can_register_or_change()
        )

    def get_code(self) -> str:
        prefix = self.type.code_prefix if self.type is not None else ""
        code = str(self.code)
        return prefix + ('0' * (self.event.ticket_code_length - len(code))) + code

    def save(self, *args, **kwargs):
        new_ticket = self.id is None
        super().save(*args, **kwargs)
        if new_ticket or self._original_status == self.status:
            return

        # Notify about the status change:
        EmailMessage(
            f"{self.event.name}: {_('Ticket')} {self.get_code()} ({_('new status')})",
            render_to_string("events/emails/ticket_changed.html", {
                'event': self.event,
                'ticket': self,
            }).strip(),
            settings.SERVER_EMAIL,
            [self.email],
            reply_to=[self.event.org_mail]
        ).send()


class Payment(BasePayment):
    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name=_("user"), null=True)
    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, verbose_name=_("ticket"))

    def __str__(self):
        if self.transaction_id:
            return f"{self.variant} ({self.id}, {self.transaction_id})"
        else:
            return f"{self.variant} ({self.id})"

    def get_finalize_url(self) -> str:
        prefix = "https://" if settings.PAYMENT_USES_SSL else "http://"
        path = reverse('ticket_payment_finalize', args=[self.event.slug, self.ticket.id, self.id])
        return prefix + settings.PAYMENT_HOST + path

    def get_failure_url(self) -> str:
        return self.get_finalize_url()

    def get_success_url(self) -> str:
        return self.get_finalize_url()

    def get_purchased_items(self) -> Iterable[PurchasedItem]:
        yield PurchasedItem(
            name=f"{self.ticket.code}: {self.ticket.name} ({self.ticket.type.name}, {self.event.name})",
            sku=self.ticket.type.name,
            quantity=1,
            price=self.ticket.type.price.amount,
            currency=self.ticket.type.price.currency)


class ApplicationType(models.Model):
    class Meta:
        verbose_name = _("application type")
        verbose_name_plural = _("application types")

    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    name = models.CharField(max_length=256, verbose_name=_("name"))
    slug = models.CharField(max_length=64, verbose_name=_("slug"))
    button_label = models.CharField(max_length=128, verbose_name=_("button label"))
    registration_from = models.DateTimeField(verbose_name=_("registration from"),
                                             help_text=_("Date/time from which users can create these applications."))
    registration_to = models.DateTimeField(verbose_name=_("registration to"),
                                           help_text=_("Date/time when the form for these applications closes."))
    description = models.TextField(verbose_name=_("description"),
                                   help_text=_("Shown on the application form. Supports Markdown."))
    template = models.TextField(verbose_name=_("template"),
                                help_text=_("Template for dynamic application form fields. Docs: ") +
                                          "https://github.com/DragoonAethis/Coriolis/wiki/Dynamic-Application-Forms")

    def __str__(self):
        return f"{self.name} ({self.id})"


class Application(models.Model):
    class Meta:
        verbose_name = _("application")
        verbose_name_plural = _("applications")
        indexes = [
            models.Index(fields=['event', 'user'])
        ]

    class ApplicationStatus(models.TextChoices):
        CANCELLED = 'CNCL', _("Cancelled")
        WAITING = 'WAIT', _("Waiting for Organizers")
        APPROVED = 'APRV', _("Approved")
        REJECTED = 'REJD', _("Rejected")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"))
    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    type = models.ForeignKey(ApplicationType, on_delete=models.RESTRICT, verbose_name=_("type"))
    status = models.CharField(max_length=4, verbose_name=_("status"),
                              choices=ApplicationStatus.choices, default=ApplicationStatus.WAITING)
    name = models.CharField(max_length=256, verbose_name=_("name"))
    phone = PhoneNumberField(verbose_name=_("phone"))
    email = models.EmailField(verbose_name=_("email"))
    application = models.TextField(verbose_name=_("application"))
    org_notes = models.TextField(verbose_name=_("org notes"))

    # Non-database fields:
    _original_status: Optional[str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def __str__(self):
        return f"{self.name} ({self.status}, {self.id})"

    def save(self, *args, **kwargs):
        new_app = self.id is None
        super().save(*args, **kwargs)
        if new_app or self._original_status == self.status:
            return

        # Notify about the status change:
        EmailMessage(
            f"{self.event.name}: {_('Application')} '{self.name}' ({_('new status')})",
            render_to_string("events/emails/application_changed.html", {
                'event': self.event,
                'application': self,
            }).strip(),
            settings.SERVER_EMAIL,
            [self.email],
            reply_to=[self.event.org_mail]
        ).send()
