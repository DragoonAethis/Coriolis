import uuid
import datetime

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    name = models.CharField(
        max_length=256,
        verbose_name=_("name"),
        help_text=_("Human-readable name for the event."),
    )
    slug = models.CharField(max_length=64, verbose_name=_("slug"), help_text=_("Short name used in links."))
    location = models.CharField(
        max_length=256,
        verbose_name=_("location"),
        help_text=_("Physical place where the event will take place."),
    )
    location_link = models.CharField(
        max_length=256,
        verbose_name=_("location link"),
        help_text=_("Link to Google Maps or OSM."),
    )
    website_link = models.CharField(
        max_length=256,
        verbose_name=_("website link"),
        help_text=_("Link to the main event website."),
    )
    contact_link = models.CharField(
        max_length=256,
        verbose_name=_("contact link"),
        help_text=_("Used for the big Contact Organizers button."),
    )
    org_mail = models.CharField(
        max_length=256,
        verbose_name=_("org mail"),
        help_text=_("Used as the Reply To address for e-mail notifications."),
    )

    date_from = models.DateTimeField(verbose_name=_("date from"))
    date_to = models.DateTimeField(verbose_name=_("date to"))
    active = models.BooleanField(
        default=True,
        verbose_name=_("event active"),
        help_text=_("If disabled, hides this event from the front page picker."),
    )

    payment_enabled = models.BooleanField(
        default=True,
        verbose_name=_("payment enabled"),
        help_text=_("Enable or disable online payments on this event."),
    )
    payment_method = models.CharField(
        blank=True,
        verbose_name=_("payment method"),
        help_text=_("Payment method to use for this event. If empty, the global default is used instead."),
    )
    emails_enabled = models.BooleanField(
        default=True,
        verbose_name=_("emails enabled"),
        help_text=_("Toggles emails for some status changes on this event."),
    )
    force_display_ticket_details_in_crew_panel = models.BooleanField(
        default=False,
        verbose_name=_("force display ticket details in crew panel"),
        help_text=_(
            "Force display all data for tickets, even if they cannot be acted upon. "
            "Useful for quick data lookups before the event."
        ),
    )

    ticket_renderer = models.ForeignKey(
        "TicketRenderer",
        verbose_name=_("ticket renderer"),
        null=True,
        on_delete=models.SET_NULL,
        help_text=_("System used to render the personalized ticket images."),
    )
    ticket_renderer_variants = models.CharField(
        max_length=256,
        blank=True,
        verbose_name=_("ticket renderer variants"),
        help_text=_("Comma-separated list of ticket variants to render. The first one will be shown to users."),
    )
    ticket_renderer_help_text = models.TextField(
        blank=True,
        verbose_name=_("ticket renderer help text"),
        help_text=_("Text to be shown under the custom image upload field (image dimensions, notices)."),
    )

    prometheus_key = models.CharField(
        max_length=256,
        blank=True,
        verbose_name=_("prometheus key"),
        help_text=_("Key used as the password for the Prometheus metrics URL"),
    )

    notice = models.TextField(
        blank=True,
        verbose_name=_("notice"),
        help_text=_("Notice to be shown below the event description, if set."),
    )
    sale_closed_notice = models.TextField(
        blank=True,
        verbose_name=_("sale closed notice"),
        help_text=_(
            "Notice to be shown instead of the default one when the ticket sales are closed. May contain HTML."
        ),
    )

    description = models.TextField(
        verbose_name=_("description"),
        help_text=_("Text shown on the main page. Supports Markdown."),
    )
    footer_content = models.TextField(
        verbose_name=_("footer content"),
        help_text=_("Muted text shown in the footer. Supports Markdown."),
    )

    ticket_code_length = models.PositiveSmallIntegerField(
        verbose_name=_("ticket code length"),
        validators=[MinValueValidator(3), MaxValueValidator(32)],
    )

    class Meta:
        verbose_name = _("event")
        verbose_name_plural = _("events")
        indexes = [models.Index(fields=["slug"])]

        permissions = [
            ("crew_accreditation", _("Can access the crew accreditation panel.")),
            ("crew_mod_queue", _("Can access the crew mod queue.")),
            ("crew_orgs", _("Can access the crew organization lists.")),
            ("crew_orgs_view_tasks", _("Can access the crew organization task lists.")),
            ("crew_orgs_view_invoices", _("Can access the org invoices from the crew panel.")),
            ("crew_orgs_view_billing_details", _("Can access the org billing details from the crew panel.")),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("event_index", kwargs={"slug": self.slug})

    def get_ticket_types_available_now(self):
        now = datetime.datetime.now()
        return self.tickettype_set.filter(
            on_site_registration=True,
            registration_from__lte=now,
            registration_to__gte=now,
            tickets_remaining__gt=0,
        ).order_by("display_order", "name")

    def get_ticket_types_available_on_site(self):
        return self.get_ticket_types_available_now().filter(on_site_registration=True)

    def get_ticket_types_available_online(self):
        return self.get_ticket_types_available_now().filter(self_registration=True)


class EventPageType(models.TextChoices):
    INFO = "info", _("Informational")
    HIDDEN_INFO = "hidden-info", _("Hidden Informational")
    TICKET_PAYMENT_INFO = "ticket-payment-info", _("Ticket Payment Instructions")


class EventPage(models.Model):
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("event"),
        help_text=_("If not set, will be shown for all events."),
    )
    name = models.CharField(max_length=256, verbose_name=_("name"))
    slug = models.CharField(
        max_length=64,
        verbose_name=_("slug"),
        help_text=_("Short name used in links. Event-specific pages have precedence."),
    )
    page_type = models.CharField(
        max_length=32,
        verbose_name=_("page type"),
        choices=EventPageType.choices,
        default=EventPageType.INFO,
        help_text=_("What this page is going to be used for?"),
    )
    hidden = models.BooleanField(
        default=False,
        verbose_name=_("hidden"),
        help_text=_("Whenever to hide this page in the page listing."),
    )
    content = models.TextField(verbose_name=_("content"), help_text=_("Page content. Supports markdown."))

    class Meta:
        verbose_name = _("event page")
        verbose_name_plural = _("event pages")
        constraints = [models.UniqueConstraint(fields=["event", "slug"], name="event_pages_with_unique_slugs")]

    def __str__(self):
        if self.event is not None:
            return f"{self.name} ({self.event.name})"
        else:
            return self.name

    def get_absolute_url(self):
        return reverse("event_page", kwargs={"slug": self.event.slug, "page_slug": self.slug})


class TicketRenderer(models.Model):
    name = models.CharField(max_length=256, verbose_name=_("name"))
    config = models.JSONField(
        blank=False,
        help_text=_("Coriolis configuration for this renderer. See wiki/docs for more info on this."),
    )

    class Meta:
        verbose_name = _("ticket renderer")
        verbose_name_plural = _("ticket renderers")

    def __str__(self):
        return f"{self.name} ({self.id})"
