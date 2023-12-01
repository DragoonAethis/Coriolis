from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import FormView, ListView

from events.forms.mod_queue import TicketModQueueDepersonalizeForm
from events.models import Event, Ticket, TicketStatus
from events.tasks.ticket_renderer import render_ticket_variants
from events.utils import delete_ticket_image


class TicketModQueueListView(ListView):
    event: Event

    model = Ticket
    paginate_by = 32  # 4 columns x 8 rows
    template_name = "events/mod_queue/list.html"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])

        if not self.request.user.is_superuser:
            messages.error(self.request, _("You don't have permissions to access this page."))
            return redirect("event_index", self.event.slug)

        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return Ticket.objects.filter(
            ~Q(nickname=None) | ~Q(image=None),
            event=self.event,
            status__in=(TicketStatus.READY, TicketStatus.WAITING_FOR_PAYMENT),
            customization_approved_by=None,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["event"] = self.event
        return context


class TicketModQueueDepersonalizeFormView(FormView):
    event: Event
    ticket: Ticket

    form_class = TicketModQueueDepersonalizeForm
    template_name = "events/mod_queue/depersonalize.html"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        self.ticket = get_object_or_404(Ticket, event=self.event, id=self.kwargs["ticket_id"])

        if not self.request.user.is_superuser:
            messages.error(self.request, _("You don't have permissions to access this page."))
            return redirect("event_index", self.event.slug)

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
        self.ticket.personalization_approved_by = None
        self.ticket.personalization_approved_on = None
        self.ticket.save()

        render_ticket_variants.send(str(self.ticket.id))

        messages.info(self.request, _("Ticket depersonalized."))
        return redirect("ticket_details", self.event.slug, self.ticket.id)
