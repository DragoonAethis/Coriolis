import uuid
from typing import Iterable

from django.db import models
from django.urls import reverse
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from payments import PurchasedItem
from payments.models import BasePayment

from events.models.users import User
from events.models.events import Event
from events.models.tickets import Ticket


class Payment(BasePayment):
    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    user = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name=_("user"), null=True)
    event = models.ForeignKey(Event, on_delete=models.RESTRICT, verbose_name=_("event"))
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, verbose_name=_("ticket"))

    def __str__(self):
        if self.transaction_id:
            return f"{self.variant} ({self.id}, {self.transaction_id})"
        else:
            return f"{self.variant} ({self.id})"

    def get_finalize_url(self) -> str:
        prefix = "https://" if settings.PAYMENT_USES_SSL else "http://"  # noqa
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
