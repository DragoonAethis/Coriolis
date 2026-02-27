import uuid
from datetime import datetime
from collections.abc import Iterable

from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from payments import PurchasedItem
from payments.models import BasePayment

from events.models.events import Event
from events.models.tickets import Ticket
from events.models.users import User


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

    refund_title = models.CharField(max_length=64, verbose_name=_("refund title"), blank=True)
    refund_data = models.JSONField(verbose_name=_("refund data"), blank=True, default=dict)

    def __str__(self):
        if self.transaction_id:
            return f"{self.variant} ({self.id}, {self.transaction_id})"
        else:
            return f"{self.variant} ({self.id})"

    def get_finalize_url(self) -> str:
        prefix = "https://" if settings.PAYMENT_USES_SSL else "http://"  # noqa
        path = reverse("ticket_payment_finalize", args=[self.event.slug, self.ticket.id, self.id])
        return prefix + settings.PAYMENT_HOST + path

    def get_failure_url(self) -> str:
        return self.get_finalize_url()

    def get_success_url(self) -> str:
        return self.get_finalize_url()

    def get_purchased_items(self) -> Iterable[PurchasedItem]:
        yield PurchasedItem(
            name=f"{self.ticket.get_code()}: {self.ticket.name} ({self.ticket.type.name}, {self.event.name})",
            sku=self.ticket.type.name,
            quantity=1,
            price=self.ticket.get_price().amount,
            currency=self.ticket.get_price().currency,
        )


class RefundRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("updated"))

    approved = models.BooleanField(verbose_name=_("approved"), default=False)
    scheduled = models.DateTimeField(verbose_name=_("scheduled"), blank=True, null=True)
    executed = models.DateTimeField(verbose_name=_("executed"), blank=True, null=True)

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, verbose_name=_("payment"))
    amount = models.DecimalField(max_digits=9, decimal_places=2, default="0.00")
    title = models.CharField(max_length=64, verbose_name=_("refund title"), blank=True)

    @transaction.atomic
    def execute(self):
        if not self.approved:
            raise RuntimeError("Refund request was not approved.")

        if self.executed:
            raise RuntimeError("Refund request was already executed.")

        if self.amount > self.payment.captured_amount:
            raise RuntimeError("Refund request cannot refund more money than was initially paid.")

        self.payment.refund_title = self.title
        self.payment.refund(amount=self.amount)

        self.executed = datetime.now()
        self.save()
