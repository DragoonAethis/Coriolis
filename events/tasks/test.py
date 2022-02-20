import dramatiq

from events.models import Ticket


@dramatiq.actor
def test_dramatiq():
    ticket_count = Ticket.objects.all().count()
    print(f"Hello, Dramatiq! Here's how many tickets we have (according to Django's ORM): {ticket_count}")
