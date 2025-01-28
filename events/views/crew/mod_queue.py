import datetime

from django.urls import reverse
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.generic import FormView, ListView

from events.forms.mod_queue import TicketModQueueDepersonalizeForm
from events.models import Event, Ticket, TicketStatus
from events.tasks.ticket_renderer import render_ticket_variants
from events.utils import delete_ticket_image, check_event_perms


class TicketModQueueListView(ListView):
    event: Event

    model = Ticket
    paginate_by = 32  # 4 columns x 8 rows
    show_all_tickets = False
    template_name = "events/mod_queue/list.html"

    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        check_event_perms(self.request, self.event, ["events.crew_mod_queue"])

        self.show_all_tickets = self.request.GET.get("all") == "1"
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        tickets = Ticket.objects.filter(
            ~Q(nickname="") | ~Q(image=""),
            event=self.event,
            status__in=(TicketStatus.READY, TicketStatus.WAITING_FOR_PAYMENT),
        )

        if not self.show_all_tickets:
            tickets = tickets.filter(customization_approved_by=None)

        return tickets.order_by("created")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["show_all_tickets"] = int(self.show_all_tickets)
        return context


class TicketModQueueDepersonalizeFormView(FormView):
    event: Event
    ticket: Ticket

    form_class = TicketModQueueDepersonalizeForm
    template_name = "events/mod_queue/depersonalize.html"

    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        check_event_perms(self.request, self.event, ["events.crew_mod_queue"])

        self.ticket = get_object_or_404(Ticket, event=self.event, id=self.kwargs["ticket_id"])
        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"event": self.event, "ticket": self.ticket})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        context["ticket"] = self.ticket
        return context

    def form_invalid(self, form):
        messages.error(self.request, _("Something went wrong... try again?"))
        return redirect("ticket_details", self.event.slug, self.ticket.id)

    def form_valid(self, form):
        if form.cleaned_data["clear_image"]:
            delete_ticket_image(self.ticket)

        if form.cleaned_data["clear_nickname"]:
            self.ticket.nickname = ""

        # If the ticket was already approved in the mod queue, revert that:
        self.ticket.customization_approved_by = None
        self.ticket.customization_approved_on = None
        self.ticket.save()

        render_ticket_variants.send(str(self.ticket.id))

        messages.info(self.request, _("Ticket depersonalized."))
        return redirect("ticket_details", self.event.slug, self.ticket.id)


@transaction.atomic
def mod_queue_approve_selected(request, slug, *args, **kwargs):
    if request.method != "POST":
        messages.error(request, _("This form accepts POST requests only."))
        return redirect("mod_queue_list", slug=slug)

    event = get_object_or_404(Event, slug=slug)
    check_event_perms(request, event, ["events.crew_mod_queue"])

    approval_ids = []
    for key, value in request.POST.items():
        if not key.startswith("approval."):
            continue

        approval_ids.append(value)

    tickets = Ticket.objects.filter(event=event, id__in=approval_ids)
    for ticket in tickets:
        ticket.customization_approved_by = request.user
        ticket.customization_approved_on = datetime.datetime.now()
        ticket.save()

    base_url = reverse("mod_queue_list", kwargs={"slug": event.slug})
    return redirect(f"{base_url}?page={request.GET.get("page") or 1}&all={request.GET.get("all") or 0}")
