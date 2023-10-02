from abc import ABC
from collections.abc import Callable

import django.http
from django.db.models import Q
from django.shortcuts import get_object_or_404

from events.models import Event, TicketStatus, TicketSource, Ticket


class Counter(ABC):
    def ingest(self, sample: dict):
        raise NotImplementedError("Override me!")

    def get_output(self):
        raise NotImplementedError("Override me!")


class GaugeCounter(Counter):
    def __init__(self, name: str, help_text: str, evaluator: Callable[[dict], bool | int]):
        self.value = 0
        self.name = name
        self.help_text = help_text
        self.evaluator = evaluator

    def ingest(self, sample: dict):
        self.value += int(self.evaluator(sample))

    def get_output(self):
        return [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} gauge",
            f"{self.name} {self.value}",
        ]


class FloatGaugeCounter(GaugeCounter):
    def ingest(self, sample: dict):
        self.value += float(self.evaluator(sample))


def prometheus_status(request, slug, key):
    event = get_object_or_404(Event, slug=slug)
    if not event.prometheus_key or key != event.prometheus_key:
        return django.http.response.HttpResponseForbidden("yeet the ayyyys")

    counters: list[Counter] = [
        GaugeCounter(
            "tickets_ready",
            "Number of tickets registered and ready for use.",
            lambda x: x["status"] == TicketStatus.READY,
        ),
        GaugeCounter(
            "tickets_used",
            "Number of used tickets.",
            lambda x: x["status"] == TicketStatus.USED,
        ),
        GaugeCounter(
            "tickets_waiting",
            "Number of tickets waiting for organizers.",
            lambda x: x["status"] == TicketStatus.WAITING,
        ),
        GaugeCounter(
            "tickets_waiting_for_payment",
            "Number of tickets waiting for payment.",
            lambda x: x["status"] == TicketStatus.WAITING_FOR_PAYMENT,
        ),
        GaugeCounter(
            "tickets_paid",
            "Number of tickets paid for before the event.",
            lambda x: x["paid"],
        ),
        GaugeCounter(
            "tickets_unpaid",
            "Number of tickets not paid for before the event.",
            lambda x: not x["paid"],
        ),
        FloatGaugeCounter(
            "tickets_value",
            "Contributed value from all tickets.",
            lambda x: x["contributed_value"],
        ),
        GaugeCounter(
            "ticket_source_admin",
            "Number of tickets created administratively.",
            lambda x: x["source"] == TicketSource.ADMIN,
        ),
        GaugeCounter(
            "ticket_source_online",
            "Number of tickets created online.",
            lambda x: x["source"] == TicketSource.ONLINE,
        ),
        GaugeCounter(
            "ticket_source_onsite",
            "Number of tickets created on site.",
            lambda x: x["source"] == TicketSource.ONSITE,
        ),
        GaugeCounter(
            "used_ticket_source_admin",
            "Number of used tickets created administratively.",
            lambda x: x["status"] == TicketStatus.USED and x["source"] == TicketSource.ADMIN,
        ),
        GaugeCounter(
            "used_ticket_source_online",
            "Number of used tickets created online.",
            lambda x: x["status"] == TicketStatus.USED and x["source"] == TicketSource.ONLINE,
        ),
        GaugeCounter(
            "used_ticket_source_onsite",
            "Number of used tickets created on-site.",
            lambda x: x["status"] == TicketStatus.USED and x["source"] == TicketSource.ONSITE,
        ),
    ]

    data = (
        Ticket.objects.filter(event_id=event.id)
        .filter(~Q(status=TicketStatus.CANCELLED))
        .values("status", "source", "paid", "contributed_value")
    )

    output_metrics = []

    for counter in counters:
        for sample in data:
            counter.ingest(sample)

        output_metrics.extend(counter.get_output())

    output_metrics.append("")  # Some tools dislike the final missing \n
    return django.http.response.HttpResponse("\n".join(output_metrics))
