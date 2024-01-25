import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _


class EventOrg(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, verbose_name=_("event"))
    owner = models.ForeignKey(get_user_model(), on_delete=models.RESTRICT, verbose_name=_("owner"))
    name = models.CharField(max_length=256, verbose_name=_("name"))
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

    def __str__(self):
        return self.name

    def has_ticket_slots_left(self):
        return self.ticket_set.count() < self.target_ticket_count


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

    def __str__(self):
        return _("Billing details #%s for %s") % str(self.id), self.name
