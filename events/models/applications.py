import uuid
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from events.models.events import Event
from events.models.users import User


class ApplicationType(models.Model):
    class Meta:
        verbose_name = _("application type")
        verbose_name_plural = _("application types")

    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    name = models.CharField(max_length=256, verbose_name=_("name"))
    slug = models.CharField(max_length=64, verbose_name=_("slug"))
    button_label = models.CharField(max_length=128, verbose_name=_("button label"))
    org_email = models.EmailField(
        verbose_name=_("org email"),
        blank=True,
        help_text=_(
            "If set, mails for these applications will be sent to the "
            "provided address, not the global event address."
        ),
    )

    registration_from = models.DateTimeField(
        verbose_name=_("registration from"),
        help_text=_("Date/time from which users can create these applications."),
    )
    registration_to = models.DateTimeField(
        verbose_name=_("registration to"),
        help_text=_("Date/time when the form for these applications closes."),
    )

    description = models.TextField(
        verbose_name=_("description"),
        help_text=_("Shown on the application form. Supports Markdown."),
    )
    template = models.TextField(
        verbose_name=_("template"),
        help_text=_("Template for dynamic application form fields. Docs: ")
        + "https://github.com/DragoonAethis/Coriolis/wiki/Dynamic-Application-Forms",
    )  # noqa

    def __str__(self):
        return f"{self.name} ({self.id})"

    def get_absolute_url(self):
        return reverse("application_form", kwargs={"slug": self.event.slug, "id": self.id})


class Application(models.Model):
    class Meta:
        verbose_name = _("application")
        verbose_name_plural = _("applications")
        indexes = [models.Index(fields=["event", "user"])]

    class ApplicationStatus(models.TextChoices):
        CANCELLED = "CNCL", _("Cancelled")
        WAITING = "WAIT", _("Waiting for Organizers")
        APPROVED = "APRV", _("Approved")
        REJECTED = "REJD", _("Rejected")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("user"))
    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    type = models.ForeignKey(ApplicationType, on_delete=models.RESTRICT, verbose_name=_("type"))
    status = models.CharField(
        max_length=4,
        verbose_name=_("status"),
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.WAITING,
    )

    name = models.CharField(max_length=256, verbose_name=_("name"))
    phone = PhoneNumberField(verbose_name=_("phone"))
    email = models.EmailField(verbose_name=_("email"))
    answers = models.JSONField(verbose_name=_("answers"))
    application = models.TextField(
        blank=True,
        verbose_name=_("application"),
        help_text=_("Legacy application answers field."),
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("notes"),
        help_text=_("User notes, visible to users/orgs"),
    )
    org_notes = models.TextField(
        blank=True,
        verbose_name=_("org notes"),
        help_text=_("Org notes, visible to users/orgs"),
    )
    private_notes = models.TextField(
        blank=True,
        verbose_name=_("private notes"),
        help_text=_("Private org notes, visible only in the admin panel"),
    )

    # Non-database fields:
    _original_status: Optional[str] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def __str__(self):
        return f"{self.name} ({self.status}, {self.id})"

    def get_absolute_url(self):
        return reverse("application_details", kwargs={"slug": self.event.slug, "app_id": self.id})

    def save(self, *args, **kwargs):
        new_app = self.id is None
        super().save(*args, **kwargs)
        if new_app or self._original_status == self.status:
            return

        # Notify about the status change:
        EmailMessage(
            _("%(event)s: Application '%(name)s' (new status)") % {"event": self.event.name, "name": self.name},
            render_to_string(
                "events/emails/application_changed.html",
                {
                    "event": self.event,
                    "application": self,
                },
            ).strip(),
            settings.SERVER_EMAIL,
            [self.email],
            reply_to=[self.type.org_email or self.event.org_mail],
        ).send()

    def get_status_class(self):
        if self.status == Application.ApplicationStatus.APPROVED:
            return "table-success"
        elif self.status in (
            Application.ApplicationStatus.REJECTED,
            Application.ApplicationStatus.CANCELLED,
        ):
            return "table-danger"
        else:
            return "table-warning"
