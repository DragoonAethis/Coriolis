from abc import ABC, abstractmethod
from collections.abc import Callable

import django.http
from django.db.models import Q
from django.shortcuts import get_object_or_404

from events.models import Event, TicketStatus, Ticket


class Counter(ABC):
    @abstractmethod
    def ingest(self, sample: dict):
        raise NotImplementedError("Override me!")

    @abstractmethod
    def get_output(self):
        raise NotImplementedError("Override me!")


class GaugeCounter(Counter):
    def __init__(
        self,
        name: str,
        help_text: str,
        evaluator: Callable[[dict], bool | int],
        bucket_by: Callable[[dict], tuple[str, ...]] | None = None,
        bucket_labels: tuple[str, ...] | None = None,
    ):
        self.name = name
        self.help_text = help_text
        self.evaluator = evaluator

        self.value = 0
        self.buckets = {}
        self.bucket_by = bucket_by
        self.bucket_labels = bucket_labels

    def accumulate_with_buckets(self, sample: dict, value):
        self.value += value

        if self.bucket_by:
            label = self.bucket_by(sample)
            self.buckets[label] = value + (self.buckets.get(label) or 0)

    def ingest(self, sample: dict):
        self.accumulate_with_buckets(sample, int(self.evaluator(sample)))

    def get_prom_labels(self, labels: tuple[str, ...]):
        return ",".join(f'{self.bucket_labels[i]}="{labels[i]}"' for i in range(len(labels)))

    def get_output(self):
        header = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} gauge",
        ]

        if self.bucket_by:
            values = [
                f"{self.name}{{{self.get_prom_labels(labels)}}} {value}" for labels, value in self.buckets.items()
            ]
        else:
            values = [f"{self.name} {self.value}"]

        return header + values


class FloatGaugeCounter(GaugeCounter):
    def ingest(self, sample: dict):
        self.accumulate_with_buckets(sample, float(self.evaluator(sample)))


def prometheus_status(request, slug, key):
    event = get_object_or_404(Event, slug=slug)
    if not event.prometheus_key or key != event.prometheus_key:
        return django.http.response.HttpResponseForbidden("yeet the ayyyys")

    counters: list[Counter] = [
        GaugeCounter(
            "ticket_counts",
            "Number of valid tickets by type/status.",
            lambda x: True,  # Filtered on the query below.
            lambda x: (str(x["type_id"]), x["source"], x["status"], x["paid"]),
            ("ticket_type", "source", "status", "paid"),
        ),
        FloatGaugeCounter(
            "tickets_value",
            "Contributed value from all tickets.",
            lambda x: x["contributed_value"],
            lambda x: (str(x["type_id"]), x["source"]),
            ("ticket_type", "source"),
        ),
    ]

    data = (
        Ticket.objects.filter(event_id=event.id)
        .filter(~Q(status=TicketStatus.CANCELLED))
        .values("type_id", "status", "source", "paid", "contributed_value")
    )

    output_metrics = []

    for counter in counters:
        for sample in data:
            counter.ingest(sample)

        output_metrics.extend(counter.get_output())

    output_metrics.append("")  # Some tools dislike the final missing \n
    return django.http.response.HttpResponse("\n".join(output_metrics))
