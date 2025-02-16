from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.db import models
from django.db.models import F, Q, Prefetch
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from events.models import EventOrg, Event, Ticket, TicketType, TicketStatus, TicketSource
from events.utils import generate_ticket_code, check_event_perms
from events.models import EventOrgTask


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
            .prefetch_related("task_set", "ticket_set", "billing_details_set")
            .annotate(tasks_done_count=models.Count("task_set", filter=Q(task_set__done=True)))
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        return context


class CrewEventOrgDetailView(DetailView):
    model = EventOrg
    template_name = "events/crew/orgs/detail.html"

    event: Event
    org: EventOrg

    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        check_event_perms(self.request, self.event, ["events.crew_orgs"])

        event_orgs = self.event.eventorg_set.prefetch_related(
            Prefetch("task_set", queryset=EventOrgTask.objects.order_by("created")),
            Prefetch("ticket_set", queryset=Ticket.objects.order_by("created")),
            "invoice_set",
            "billing_details_set",
        ).annotate(
            tasks_done_count=models.Count("task_set", filter=Q(task_set__done=True))
        )

        self.org = get_object_or_404(event_orgs, id=self.kwargs["org_id"])
        return super().dispatch(*args, **kwargs)

    def get_object(self, queryset=None):
        return self.org

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["org"] = self.org
        context["is_owner"] = self.org.owner == self.request.user
        return context


@transaction.atomic
def crew_event_org_generate_tickets(request, slug, org_id: str, *args, **kwargs):
    if request.method != "POST":
        messages.error(request, _("This form accepts POST requests only."))
        return redirect("event_index", slug=slug)

    event = get_object_or_404(Event, slug=slug)
    check_event_perms(request, event, ["events.crew_accreditation"])

    count = int(request.POST["count"])

    if count < 1:
        messages.error(request, _("How many tickets do you want to generate?"))
        return redirect("crew_orgs_details", slug, org_id)

    if count > 20:
        messages.error(request, _("You're overdoing it!"))
        return redirect("crew_orgs_details", slug, org_id)

    try:
        ttype = TicketType.objects.get(id=request.POST["type"])
        if ttype not in event.get_ticket_types_available_on_site():
            raise TicketType.DoesNotExist()
    except TicketType.DoesNotExist:
        messages.error(request, _("Ticket type not found, or not valid for this event on-site!"))
        return redirect("crew_orgs_details", slug, org_id)

    if ttype.tickets_remaining < count:
        messages.error(request, _("We ran out of these tickets."))
        return redirect("crew_orgs_details", slug, org_id)

    is_of_age = request.POST.get("is_of_age") == "1"

    codes = []
    for i in range(count):
        t = Ticket(
            user=request.user,
            event=event,
            type=ttype,
            org_id=org_id,
            name=_("Generated Ticket"),
            status=TicketStatus.USED,
            source=TicketSource.ONSITE,
            age_gate=is_of_age,
            code=generate_ticket_code(event),
        )

        t.save()
        codes.append(t.get_code())

    ttype.tickets_remaining = F("tickets_remaining") - 1
    ttype.save()

    messages.success(request, _("Success - tickets created: ") + ", ".join(codes))
    return redirect("crew_orgs_details", slug, org_id)


@transaction.atomic
def crew_event_org_add_task(request, slug, org_id: str, *args, **kwargs):
    if request.method != "POST":
        messages.error(request, _("This form accepts POST requests only."))
        return redirect("event_index", slug=slug)

    event = get_object_or_404(Event, slug=slug)
    check_event_perms(request, event, ["events.crew_orgs_view_tasks"])

    content = request.POST["name"].strip()
    if not content:
        messages.error(request, _("Provide a task name to add."))
        return redirect("crew_orgs_details", slug, org_id)
 
    task = EventOrgTask(
        updated_by=request.user,
        event=event,
        event_org_id=org_id,
        name=content,
        done=False,
    )

    task.save()
    return redirect("crew_orgs_details", slug, org_id)


@transaction.atomic
def crew_event_org_update_task(request, slug, org_id: str, task_id: str, *args, **kwargs):
    if request.method != "POST":
        messages.error(request, _("This form accepts POST requests only."))
        return redirect("event_index", slug=slug)

    event = get_object_or_404(Event, slug=slug)
    check_event_perms(request, event, ["events.crew_orgs_view_tasks"])

    task = EventOrgTask.objects.get(id=task_id, event_org_id=org_id)
    task.updated_by = request.user
    task.notes = request.POST["task_notes"]
    task.done = not task.done

    task.save()
    return redirect("crew_orgs_details", slug, org_id)


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
