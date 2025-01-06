import uuid

from django.core.mail import EmailMessage
from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from events.models.events import Event
from events.models.users import User
from events.utils import validate_multiple_emails


class ApplicationType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    name = models.CharField(max_length=256, verbose_name=_("name"))
    slug = models.CharField(max_length=64, verbose_name=_("slug"))
    button_label = models.CharField(max_length=128, verbose_name=_("button label"))
    org_emails = models.CharField(
        db_column="org_email",
        verbose_name=_("org emails"),
        blank=True,
        help_text=_(
            "If set, mails for these applications will be sent to the "
            "provided addresses, not the global event address. This can "
            "be a comma-separated list of emails."
        ),
        validators=[validate_multiple_emails],
    )

    registration_from = models.DateTimeField(
        verbose_name=_("registration from"),
        help_text=_("Date/time from which users can create these applications."),
    )
    registration_to = models.DateTimeField(
        verbose_name=_("registration to"),
        help_text=_("Date/time when the form for these applications closes."),
    )
    requires_valid_ticket = models.BooleanField(
        default=False,
        verbose_name=_("requires registration"),
        help_text=_("If enabled, users must have a valid ticket for the event before sending applications."),
    )
    display_deadline = models.BooleanField(
        default=False,
        verbose_name=_("display deadline"),
        help_text=_("Publicly display the application form closure date."),
    )

    description = models.TextField(
        verbose_name=_("description"),
        help_text=_("Shown on the application form. Supports Markdown."),
    )
    template = models.TextField(
        verbose_name=_("template"),
        help_text=_(
            "Template for dynamic application form fields. Docs: "
            "https://github.com/DragoonAethis/Coriolis/wiki/Dynamic-Application-Forms"
        ),
    )
    submission_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("submission message"),
        help_text=_(
            "Message to be displayed after successfully submitting a form. "
            "If empty, a default 'orgs will be in touch soon' message is shown."
        ),
    )

    class Meta:
        verbose_name = _("application type")
        verbose_name_plural = _("application types")

    def __str__(self):
        return f"{self.name} ({self.id})"

    def get_absolute_url(self):
        return reverse("application_form", kwargs={"slug": self.event.slug, "id": self.id})


class Application(models.Model):
    class ApplicationStatus(models.TextChoices):
        CANCELLED = "CNCL", _("Cancelled")
        WAITING = "WAIT", _("Waiting for Organizers")
        RESERVE = "RSVE", _("On Reserve List")
        APPROVED = "APRV", _("Accepted")
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
    banner = models.TextField(
        blank=True,
        verbose_name=_("banner"),
        help_text=_("Banner/MOTD (uses Markdown), visible to users on the front page and in the application details"),
    )

    class Meta:
        verbose_name = _("application")
        verbose_name_plural = _("applications")
        indexes = [models.Index(fields=["event", "user"])]

    # Non-database fields:
    _original_status: str | None = None

    def __str__(self):
        return f"{self.name} ({self.status}, {self.id})"

    def save(self, *args, **kwargs):
        new_app = self.id is None
        super().save(*args, **kwargs)
        if new_app or self._original_status == self.status:
            return

        # Notify about the status change:
        EmailMessage(
            subject=_("%(event)s: Application '%(name)s' (new status)") % {"event": self.event.name, "name": self.name},
            body=render_to_string(
                "events/emails/application_changed.html",
                {
                    "event": self.event,
                    "application": self,
                },
            ).strip(),
            to=[self.email],
            reply_to=self.get_org_emails(),
        ).send()

    def get_absolute_url(self):
        return reverse("application_details", kwargs={"slug": self.event.slug, "app_id": self.id})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def get_org_emails(self) -> list[str]:
        if self.type.org_emails:
            return [mail.strip() for mail in self.type.org_emails.split(",")]
        else:
            return [self.event.org_mail]

    def get_notification_emails(self) -> list[str]:
        return [self.email] + self.get_org_emails()

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
