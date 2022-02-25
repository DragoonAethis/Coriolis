import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator


class Event(models.Model):
    class Meta:
        verbose_name = _("event")
        verbose_name_plural = _("events")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

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
    emails_enabled = models.BooleanField(default=True, verbose_name=_("emails enabled"),
                                         help_text=_("Toggles emails for some status changes on this event."))
    prometheus_key = models.CharField(max_length=256, blank=True, verbose_name=_("prometheus key"),
                                      help_text=_("Key used as the password for the Prometheus metrics URL"))
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

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

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
