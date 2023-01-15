import logging
from datetime import datetime, timedelta

import django.db.utils
from django.db.models import F
from django.contrib import messages
from django.core.cache import caches
from django.core.mail import EmailMessage
from django.contrib.humanize.templatetags.humanize import naturaltime
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
from events.tasks.ticket_renderer import render_ticket_variants
from events.utils import (
    get_ticket_purchase_rate_limit_keys,
    generate_ticket_code,
    delete_ticket_image,
    save_ticket_image,
)


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

        now = datetime.now()

        if not self.type.registration_from < now:
            messages.error(self.request, _("Online sales of this ticket type have not yet started."))
            return False

        if not now < self.type.registration_to:
            messages.error(self.request, _("Online sales of this ticket type have ended."))
            return False

        if self.type.purchase_rate_limit_secs > 0:
            rate_limit_keys = get_ticket_purchase_rate_limit_keys(self.request, self.type)
            rate_limit_cache = caches[settings.TICKET_PURCHASE_RATE_LIMIT_CACHE_NAME]

            rate_limits_hit = [
                gate_date
                for gate_date in [rate_limit_cache.get(key) for key in rate_limit_keys]
                if gate_date is not None and now < gate_date
            ]

            if any(rate_limits_hit):
                deadline = max(rate_limits_hit)
                messages.error(
                    self.request,
                    _("Slow down! You can purchase another ticket of this type %(in_how_long)s.") % {
                        'in_how_long': naturaltime(deadline)
                    }
                )

                return False

        return True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"event": self.event, "ticket_type": self.type})
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
                _("Notes for ticket: '%(code)s'") % {
                    'code': ticket.get_code()
                },
                _("A new ticket was registered with the following notes: ") + ticket.notes,
                settings.SERVER_EMAIL,
                [ticket.event.org_mail],
                reply_to=[ticket.email]
            ).send(fail_silently=True)
        elif self.type.must_pay_online:
            ticket.status = TicketStatus.WAITING_FOR_PAYMENT
            ticket._original_status = TicketStatus.WAITING_FOR_PAYMENT

        try:
            self.type.tickets_remaining = F('tickets_remaining') - 1
            self.type.save()
        except django.db.utils.IntegrityError:
            messages.error(self.request, _("We ran out of these tickets."))
            return redirect('event_index', self.event.slug)

        try:
            ticket.save()
        except Exception as ex:  # noqa
            logging.exception("Could not save a new ticket, bumping back the remaining tickets counter...")
            self.type.tickets_remaining = F('tickets_remaining') + 1
            self.type.save()

            messages.error(self.request, _("Could not save a new ticket - please contact event support."))
            return redirect('event_index', self.event.slug)

        render_ticket_variants.send(str(ticket.id))

        EmailMessage(
            _("%(event)s: Ticket '%(code)s'") % {
                'event': self.event.name,
                'code': ticket.get_code()
            },
            render_to_string("events/emails/thank_you.html", {
                'event': self.event,
                'ticket': ticket,
                'is_waiting': ticket.status == TicketStatus.WAITING
            }).strip(),
            settings.SERVER_EMAIL,
            [ticket.email],
            reply_to=[ticket.event.org_mail]
        ).send(fail_silently=True)

        # Keep track of the rate limits for high-demand tickets:
        if self.type.purchase_rate_limit_secs > 0:
            rate_limit_keys = get_ticket_purchase_rate_limit_keys(self.request, self.type)
            rate_limit_cache = caches[settings.TICKET_PURCHASE_RATE_LIMIT_CACHE_NAME]
            deadline = datetime.now() + timedelta(seconds=self.type.purchase_rate_limit_secs)

            for key in rate_limit_keys:
                rate_limit_cache.set(key, deadline, timeout=self.type.purchase_rate_limit_secs)

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

        ticket_type = TicketType.objects.get(id=self.ticket.type_id)
        ticket_type.tickets_remaining += 1
        ticket_type.save()

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
                save_ticket_image(self.request, self.ticket, form.cleaned_data['image'])

        if shirt_size := form.cleaned_data.get('shirt_size'):
            self.ticket.shirt_size = shirt_size

        self.ticket.save()
        messages.info(self.request, _("Changes were saved and your ticket is now being generated. "
                                      "Refresh this page in a few minutes to see the preview."))
        render_ticket_variants.send(str(self.ticket.id))

        return redirect('ticket_details', self.event.slug, self.ticket.id)

    def get(self, request, *args, **kwargs):
        # How did you get here...?
        messages.warning(request, _("Something went wrong - try again."))
        return redirect('ticket_details', self.event.slug, self.ticket.id)
