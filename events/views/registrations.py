import datetime

from django.db.models import F
from django.contrib import messages
from django.core.mail import EmailMessage
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.views.generic import FormView
from django.conf import settings
from django.utils.html import mark_safe

from events.forms import RegistrationForm, CancelRegistrationForm, UpdateTicketForm
from events.models import Event, TicketType, Ticket, TicketStatus, TicketSource
from events.utils import generate_ticket_code, delete_ticket_image, save_ticket_image


class RegistrationView(FormView):
    event: Event
    type: TicketType

    form_class = RegistrationForm
    template_name = 'events/tickets/register.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs['slug'])
        self.type = get_object_or_404(TicketType, event=self.event, id=self.kwargs['id'])

        if not self.validate_ticket_type():
            return redirect('event_index', self.event.slug)

        return super().dispatch(*args, **kwargs)

    def validate_ticket_type(self) -> bool:
        """Check whenever the current ticket type can be purchased online."""

        if self.type.event_id != self.event.id:
            messages.error(self.request, _("This ticket type cannot be sold for this event!"))
            return False

        if not self.type.self_registration:
            messages.error(self.request, _("You cannot purchase a ticket of this type online."))
            return False

        if self.type.tickets_remaining <= 0:
            messages.error(self.request, _("We ran out of these tickets."))
            return False

        now = datetime.datetime.now()

        if not self.type.registration_from < now:
            messages.error(self.request, _("Online sales of this ticket type have not yet started."))
            return False

        if not now < self.type.registration_to:
            messages.error(self.request, _("Online sales of this ticket type have ended."))
            return False

        return True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"event": self.event, "type": self.type})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'event': self.event, 'type': self.type})
        return context

    def form_valid(self, form):
        ticket = Ticket(user=self.request.user,
                        event=self.event,
                        type=self.type,
                        status=TicketStatus.READY_PAY_ON_SITE,
                        source=TicketSource.ONLINE,
                        name=form.cleaned_data['name'],
                        email=form.cleaned_data['email'],
                        phone=form.cleaned_data['phone'],
                        age_gate=form.cleaned_data['age_gate'],
                        nickname=form.cleaned_data['nickname'],
                        notes=form.cleaned_data.get('notes'))

        try:
            ticket.code = generate_ticket_code(self.event)
        except ValueError as ex:
            messages.error(self.request, str(ex))
            return redirect('event_index', self.event.slug)

        if ticket.notes is not None and len(ticket.notes) > 0:
            ticket.status = TicketStatus.WAITING
            ticket._original_status = TicketStatus.WAITING
            EmailMessage(
                f"{_('Notes for ticket')}: {ticket.get_code()}",
                _("A new ticket was registered with the following notes: ") + ticket.notes,
                settings.SERVER_EMAIL,
                [ticket.event.org_mail],
                reply_to=[ticket.email]
            ).send(fail_silently=True)
        elif self.type.must_pay_online:
            ticket.status = TicketStatus.WAITING_FOR_PAYMENT
            ticket._original_status = TicketStatus.WAITING_FOR_PAYMENT

        if form.cleaned_data['image']:
            save_ticket_image(ticket, form.cleaned_data['image'])

        ticket.save()

        EmailMessage(
            f"{self.event.name}: {_('Ticket')} {ticket.get_code()}",
            render_to_string("events/emails/thank_you.html", {
                'event': self.event,
                'ticket': ticket,
                'is_waiting': ticket.status == TicketStatus.WAITING
            }).strip(),
            settings.SERVER_EMAIL,
            [ticket.email],
            reply_to=[ticket.event.org_mail]
        ).send(fail_silently=True)

        self.type.tickets_remaining = F('tickets_remaining') - 1
        self.type.save()

        if ticket.status == TicketStatus.WAITING_FOR_PAYMENT:
            messages.success(self.request, _("Thank you for your registration! You must pay for the selected ticket "
                                             "type online. Do so now, or click Pay Online later from your tickets."))
            return redirect('ticket_payment', self.event.slug, ticket.id)
        elif ticket.status == TicketStatus.WAITING:
            messages.success(self.request, _("Thank you for your registration! You will receive an e-mail when "
                                             "organizers read and acknowledge your ticket notes."))
        elif ticket.status == TicketStatus.READY_PAY_ON_SITE:
            messages.success(self.request, _("Thank you for your registration! You can see your ticket details below."))

        return redirect('event_index', self.event.slug)


class CancelRegistrationView(FormView):
    event: Event
    ticket: Ticket

    form_class = CancelRegistrationForm
    template_name = 'events/tickets/cancel.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs['slug'])
        self.ticket = get_object_or_404(Ticket, event=self.event, id=self.kwargs['ticket_id'])

        if self.request.user.id != self.ticket.user_id:
            messages.error(self.request, _("You cannot cancel a ticket that is not yours!"))
            return redirect('event_index', self.event.slug)

        if self.ticket.status not in (TicketStatus.READY_PAY_ON_SITE, TicketStatus.WAITING_FOR_PAYMENT):
            messages.error(self.request, _("Cannot cancel a ticket with this status - please contact the organizers."))
            return redirect('event_index', self.event.slug)

        if self.ticket.payment_set.count() != 0:
            messages.error(self.request, _("This ticket has attached payments - please contact the organizers."))
            return redirect('event_index', self.event.slug)

        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'event': self.event, 'ticket': self.ticket})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'event': self.event, 'ticket': self.ticket})
        return context

    def form_valid(self, form):
        self.ticket.status = TicketStatus.CANCELLED
        self.ticket.save()

        type = TicketType.objects.get(id=self.ticket.type_id)
        type.tickets_remaining += 1
        type.save()

        messages.info(self.request, _("Ticket cancelled."))
        return redirect('event_index', self.event.slug)


class UpdateTicketView(FormView):
    event: Event
    ticket: Ticket

    form_class = UpdateTicketForm
    template_name = 'events/tickets/details.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=self.kwargs['slug'])
        self.ticket = get_object_or_404(Ticket, event=self.event, id=self.kwargs['ticket_id'])

        if self.request.user.id != self.ticket.user_id:
            messages.error(self.request, _("You cannot change a ticket that is not yours!"))
            return redirect('ticket_details', self.event.slug, self.ticket.id)

        if not self.ticket.can_personalize():
            messages.error(self.request, _("This ticket can no longer be changed."))
            return redirect('ticket_details', self.event.slug, self.ticket.id)

        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"event": self.event, "ticket": self.ticket})
        return kwargs

    def form_invalid(self, form):
        # TODO: Reconsider this... Maybe convert the ticket details view into a FormView?
        errors = ['<ul class="mb-0">']
        for field, field_errors in form.errors.items():
            for error in field_errors:
                errors.append(f"<li><b>{form.fields[field].label}</b>: {error}</li>")
        errors.append("</ul>")

        messages.error(self.request, mark_safe("".join(errors)))
        return redirect('ticket_details', self.event.slug, self.ticket.id)

    def form_valid(self, form):
        self.ticket.nickname = form.cleaned_data['nickname']

        if not form.cleaned_data['keep_current_image']:
            delete_ticket_image(self.ticket)

            if form.cleaned_data['image']:
                save_ticket_image(self.ticket, form.cleaned_data['image'])

        self.ticket.save()
        return redirect('ticket_details', self.event.slug, self.ticket.id)

    def get(self, request, *args, **kwargs):
        # How did you get here...?
        messages.warning(request, _("Something went wrong - try again."))
        return redirect('ticket_details', self.event.slug, self.ticket.id)
