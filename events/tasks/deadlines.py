from datetime import datetime

import dramatiq
from django.utils.translation import gettext_lazy as _
from dramatiq_crontab import cron

from events.models.tickets import Ticket, TicketStatus


@cron("*/15 * * * *")  # Every 15mins
@dramatiq.actor
def collect_dead_tickets():
    dead_tickets = (
        Ticket.objects.filter(event__active=True).filter(status_deadline__lt=datetime.now()).select_related("event")
    )

    cancelled_tickets = 0

    for ticket in dead_tickets:
        if ticket.status == TicketStatus.WAITING_FOR_PAYMENT:
            ticket.status_deadline = None
            ticket.status = TicketStatus.CANCELLED
            ticket.notes = _("[System] The ticket was not paid for in time.") + "\n" + ticket.notes
            ticket.save(update_fields=["status_deadline", "status", "notes"])
            cancelled_tickets += 1

    collect_dead_tickets.logger.info(f"Cancelled {cancelled_tickets} ticket(s).")
