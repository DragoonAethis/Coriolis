import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.files.storage import storages
from django.shortcuts import reverse

from djmoney.money import Money
from djmoney.models.fields import MoneyField


class EventOrg(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, verbose_name=_("event"))
    owner = models.ForeignKey(get_user_model(), on_delete=models.RESTRICT, verbose_name=_("owner"))
    name = models.CharField(max_length=256, verbose_name=_("name"))
    location_tag = models.CharField(
        blank=True,
        max_length=256,
        verbose_name=_("location tag"),
        help_text=_("Map location or another identifier that makes it easier to locate this org in on-site operations.")
    )

    source_application = models.ForeignKey(
        "events.Application",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("source application"),
    )

    target_ticket_type = models.ForeignKey(
        "events.TicketType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    target_ticket_count = models.PositiveSmallIntegerField(
        verbose_name=_("target ticket count"),
    )

    class Meta:
        verbose_name = _("event org")
        verbose_name_plural = _("event orgs")

    def __str__(self):
        return f"{self.name} ({self.event.name})"

    def get_absolute_url(self):
        return reverse("crew_orgs_details", kwargs={"slug": self.event.slug, "org_id": self.id})

    def has_ticket_slots_left(self):
        return self.ticket_set.count() < self.target_ticket_count

    def has_all_tickets_used(self):
        return self.ticket_set.count() > 0 and all(ticket.status == "USED" for ticket in self.ticket_set.all())

    def has_all_tasks_done(self):
        return self.task_set.count() > 0 and all(task.done for task in self.task_set.all())


class EventOrgTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))
    updated_by = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.RESTRICT, verbose_name=_("updated by"))

    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="task_set",
        verbose_name=_("event"),
    )
    event_org = models.ForeignKey(
        "events.EventOrg",
        on_delete=models.CASCADE,
        related_name="task_set",
        verbose_name=_("event org"),
    )

    name = models.CharField(
        max_length=256,
        verbose_name=_("name"),
        help_text=_("Large task name displayed in the org overview"),
    )
    done = models.BooleanField(
        default=False,
        verbose_name=_("done"),
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("notes"),
        help_text=_("Extra notes displayed under the task"),
    )

    def __str__(self):
        return self.name


class EventOrgBillingDetails(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="billing_details_set",
        verbose_name=_("event"),
    )
    event_org = models.ForeignKey(
        "events.EventOrg",
        on_delete=models.CASCADE,
        related_name="billing_details_set",
        verbose_name=_("event org"),
    )

    name = models.CharField(max_length=256, verbose_name=_("name"))
    tax_id = models.CharField(
        max_length=32,
        verbose_name=_("tax identifier"),
    )
    address = models.CharField(max_length=256, verbose_name=_("address"))
    postcode = models.CharField(max_length=256, verbose_name=_("postcode"))
    city = models.CharField(max_length=256, verbose_name=_("city"))
    representative = models.CharField(max_length=256, verbose_name=_("representative"))

    class Meta:
        verbose_name = _("event org billing details")
        verbose_name_plural = _("event org billing details")

    def __str__(self):
        return _("Billing details #%s for %s") % (str(self.id), self.name)


def get_invoice_upload_dir(instance: "EventOrgInvoice", filename: str):
    return f"{instance.event.slug}/invoices/{filename}"


class EventOrgInvoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="invoice_set",
        verbose_name=_("event"),
    )
    event_org = models.ForeignKey(
        "events.EventOrg",
        on_delete=models.CASCADE,
        related_name="invoice_set",
        verbose_name=_("event org"),
    )

    name = models.CharField(
        max_length=256,
        verbose_name=_("name"),
        help_text=_("User-friendly invoice name, without the document number/ID."),
    )
    tag = models.CharField(
        blank=True,
        max_length=256,
        verbose_name=_("tag"),
        help_text=_("Machine-friendly invoice name, useful for automation, without the document number/ID."),
    )
    document_id = models.CharField(
        max_length=256,
        verbose_name=_("document ID"),
        help_text=_("The invoice number or document ID. Should be unique within the issuing legal entity."),
    )
    file = models.FileField(
        blank=True,
        upload_to=get_invoice_upload_dir,
        storage=storages["private"],
        verbose_name=_("file"),
        help_text=_("Downloadable file with the invoice contents."),
    )

    net_value = MoneyField(
        max_digits=16,
        decimal_places=2,
        verbose_name=_("net value"),
        help_text=_("Net value on the invoice. Used for statistics."),
        default=Money(0, settings.CURRENCY),
        default_currency=settings.CURRENCY,
    )
    tax_value = MoneyField(
        max_digits=16,
        decimal_places=2,
        verbose_name=_("tax value"),
        help_text=_("Tax value (VAT, etc) on the invoice. Used for statistics."),
        default=Money(0, settings.CURRENCY),
        default_currency=settings.CURRENCY,
    )
    gross_value = MoneyField(
        max_digits=16,
        decimal_places=2,
        verbose_name=_("gross value"),
        help_text=_("Gross value on the invoice. Used for statistics."),
        default=Money(0, settings.CURRENCY),
        default_currency=settings.CURRENCY,
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_("notes"),
        help_text=_("Additional notes visible to org owners."),
    )

    def __str__(self):
        return f"{self.name} {self.document_id}"
