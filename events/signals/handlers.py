from django.dispatch import receiver
from djmoney.money import Money
from payments import PaymentStatus
from payments.signals import status_changed


@receiver(status_changed)
def handle_payment_status_change(sender: type, **kwargs):
    from events.models import Payment, Ticket, TicketStatus

    payment: Payment = kwargs.get("instance")
    if payment is None:
        raise ValueError("The status change was signalled for an unknown Payment.")

    ticket: Ticket = payment.ticket

    if payment.status == PaymentStatus.CONFIRMED:
        ticket.contributed_value += Money(
            payment.captured_amount, payment.currency or ticket.contributed_value.currency
        )

        ticket.status = TicketStatus.READY
        ticket.status_deadline = None
        ticket.paid = True
        ticket.save()


def connect_signals():
    """Just make sure this module is imported for now, since we
    connect all signals via @receiver annotations."""
    pass
