from django.shortcuts import get_object_or_404
from django.views.generic import ListView

from events.models import EventOrg, Event, Ticket
from events.utils import check_event_perms


class CrewEventOrgListView(ListView):
    model = EventOrg
    template_name = "events/crew/orgs/list.html"

    event: Event

    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        check_event_perms(self.request, self.event, ["events.crew_orgs"])

        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return (
            EventOrg.objects.filter(event=self.event)
            .select_related("owner", "target_ticket_type")
            .prefetch_related("ticket_set", "billing_details_set")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        return context


class CrewEventOrgTicketListView(ListView):
    model = Ticket
    template_name = "events/crew/orgs/tickets.html"

    event: Event
    org: EventOrg

    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        check_event_perms(self.request, self.event, ["events.crew_orgs", "events.crew_accreditation"])

        self.org = get_object_or_404(EventOrg, id=self.kwargs["org_id"])
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return self.org.ticket_set.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["org"] = self.org
        return context
