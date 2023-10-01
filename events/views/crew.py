from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q, F
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import FormView

from events.forms.crew import CrewNewTicketForm, CrewFindTicketForm, CrewUseTicketForm
from events.models import Event, Ticket, TicketType, TicketStatus, TicketSource
from events.models.notifications import NotificationChannelSource
from events.tasks.notifications import notify_channel
from events.utils import generate_ticket_code


class CrewIndexNewView(FormView):
    event: Event

    form_class = CrewNewTicketForm
    template_name = "events/crew/index.html"

    @method_decorator(user_passes_test(lambda u: u.is_staff))
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "event": self.event,
                "types": list(TicketType.objects.filter(event_id=self.event.id, on_site_registration=True)),
            }
        )
        return kwargs

    def get_context_data(self, **kwargs):
        context: dict = super().get_context_data(**kwargs) or {}

        context.update({"event": self.event, "find_form": CrewFindTicketForm(event=self.event)})

        return context

    def form_valid(self, form):
        type_id = form.cleaned_data["ticket_type"]
        ticket_type = TicketType.objects.get(id=int(type_id))

        if ticket_type.tickets_remaining <= 0:
            messages.error(self.request, _("We ran out of these tickets."))
            return redirect("crew_index", self.event.slug)

        t = Ticket(
            user=self.request.user,
            event=self.event,
            type=ticket_type,
            name=_("Generated Ticket"),
            status=TicketStatus.USED,
            source=TicketSource.ONSITE,
            age_gate=form.cleaned_data["age_gate"],
            code=generate_ticket_code(self.event),
        )

        t.save()

        ticket_type.tickets_remaining = F("tickets_remaining") - 1
        ticket_type.save()

        messages.success(self.request, _("Success - ticket created: ") + t.get_code())
        return redirect("crew_index", self.event.slug)


class CrewFindTicketView(FormView):
    event: Event

    form_class = CrewFindTicketForm
    template_name = "events/crew/list.html"

    @method_decorator(user_passes_test(lambda u: u.is_staff))
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"event": self.event})
        return kwargs

    def form_valid(self, form):
        text_query = form.cleaned_data["query"]

        try:  # Maybe it's a code?
            maybe_code_query = int(text_query)
            if (10**self.event.ticket_code_length) < maybe_code_query:
                raise ValueError("Value not in the ticket code range for this event")

            ticket = Ticket.objects.get(event_id=self.event.id, code=maybe_code_query)
            if ticket.event_id != self.event.id:
                raise ValueError("Ticket not valid for this event")

            return redirect("crew_existing_ticket", self.event.slug, ticket.id)
        except ValueError:
            # Well, perhaps not.
            pass
        except Ticket.DoesNotExist:
            messages.warning(
                self.request,
                _("Ticket with the provided code does not exist - searching..."),
            )

        query = Q(user__email__icontains=text_query)
        for field in ("name", "email", "phone", "nickname", "notes"):
            query |= Q(**{f"{field}__icontains": text_query})

        try:
            tickets = list(Ticket.objects.filter(event_id=self.event.id).filter(query))
            if len(tickets) == 0:
                messages.error(self.request, _("No tickets found."))
                return redirect("crew_index", self.event.slug)
            elif len(tickets) == 1:
                ticket = tickets[0]
                messages.info(self.request, _("Found a single ticket."))
                return redirect("crew_existing_ticket", self.event.slug, ticket.id)
            else:
                return render(
                    self.request,
                    "events/crew/list.html",
                    {"event": self.event, "form": form, "tickets": tickets},
                )
        except Ticket.DoesNotExist:
            messages.error(self.request, _("Ticket with the provided code does not exist."))
            return redirect("crew_index", self.event.slug)


class CrewExistingTicketView(FormView):
    event: Event
    ticket: Ticket
    horrible_error: Optional[str]

    form_class = CrewUseTicketForm
    template_name = "events/crew/ticket.html"

    @method_decorator(user_passes_test(lambda u: u.is_staff))
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs["slug"])
        self.ticket = get_object_or_404(Ticket, id=self.kwargs["ticket_id"])
        self.horrible_error = None

        if self.ticket.event_id != self.event.id:
            messages.error(self.request, _("This ticket is not valid for this event!"))
            return redirect("crew_index", self.event.slug)

        if self.ticket.status == TicketStatus.USED:
            self.horrible_error = _("This ticket has already been used.")
        elif self.ticket.status == TicketStatus.CANCELLED:
            self.horrible_error = _("This ticket has been cancelled.")
        elif self.ticket.status != TicketStatus.READY:
            self.horrible_error = _("This ticket has an invalid status: ") + self.ticket.get_status_display()

        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context: dict = super().get_context_data(**kwargs) or {}

        other_user_tickets = list(
            Ticket.objects.filter(user_id=self.ticket.user.id).filter(event_id=self.event.id).exclude(id=self.ticket.id)
        )

        context.update(
            {
                "event": self.event,
                "ticket": self.ticket,
                "other_tickets": other_user_tickets,
                "horrible_error": self.horrible_error,
            }
        )

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"event": self.event, "ticket": self.ticket})

        return kwargs

    def form_valid(self, form):
        self.ticket.status = TicketStatus.USED
        self.ticket.save()

        if self.ticket.paid:
            notify_channel.send(
                str(self.event.id),
                NotificationChannelSource.TICKET_USED,
                {"ticket_id": str(self.ticket.id)},
            )

        return redirect("crew_index", self.event.slug)
