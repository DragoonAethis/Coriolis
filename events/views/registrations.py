import datetime
import math
import random
import uuid

from django.contrib import messages
from django.core.mail import send_mail, EmailMessage
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.views.generic import FormView
from django.conf import settings

from events.forms import RegistrationForm, CancelRegistrationForm
from events.models import Event, TicketType, Ticket


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
                        status=Ticket.TicketStatus.READY_PAY_ON_SITE,
                        name=form.cleaned_data['name'],
                        email=form.cleaned_data['email'],
                        phone=form.cleaned_data['phone'],
                        nickname=form.cleaned_data['nickname'],
                        city=form.cleaned_data['city'])

        # Now for the nasty part: Get ALL the ticket numbers we already
        # have in the database and generate a new one that does not
        # conflict with any existing ones.
        maximum_tickets = 10 ** self.event.ticket_code_length
        numbers = set(Ticket.objects.filter(event_id=self.event.id).values_list('code', flat=True))

        if len(numbers) >= maximum_tickets:
            # Yeah, we're not even gonna try.
            messages.error(self.request, _("MAXIMUM TICKET CODES REACHED! Contact event organizers with this message."))
            return redirect('event_index', self.event.slug)

        # Try to generate a new code - scale the maximum number of attempts
        # with the current ticket code count to avoid the slow path:
        selected_code = None
        for i in range(10 ** int(math.log10(max(10, len(numbers))))):
            generated_code = random.randint(0, maximum_tickets - 1)
            if generated_code not in numbers:
                selected_code = generated_code
                break  # We've got a unique code, good!

        if selected_code is None:
            # Okay, do it the hard way. This is VERY slow with long codes.
            possible_numbers = set(range(maximum_tickets - 1)) - numbers
            assert len(possible_numbers) > 0

            # This 100% gets us any valid remaining ticket code.
            selected_code = random.choice(list(possible_numbers))

        ticket.code = selected_code

        ticket.notes = (form.cleaned_data.get('notes') or "").strip()
        if len(ticket.notes) > 0:
            ticket.status = Ticket.TicketStatus.WAITING
            EmailMessage(
                f"{_('Notes for ticket')}: {ticket.get_code()}",
                _("A new ticket was registered with the following notes: ") + ticket.notes,
                settings.SERVER_EMAIL,
                [settings.SERVER_EMAIL],
                reply_to=[ticket.email]
            ).send(fail_silently=True)

        if 'image' in self.request.FILES:
            from PIL import Image

            file: UploadedFile = form.cleaned_data['image']
            path = f'ticketavatars/{uuid.uuid4()}.png'
            ticket.image = default_storage.save(path, file)

            # Do post-processing. We need to do this after saving the
            # file once to prevent annoying issues with in-memory PIL...
            image: Image = Image.open(ticket.image.file)
            # TODO: Image post-processing should land here once we have reqs.

            # And now, save the image once again.
            with default_storage.open(ticket.image.name, 'wb') as handle:
                image.save(handle, 'png')

        messages.success(self.request, _("Thank you for your registration! You can see your ticket details below."))
        ticket.save()

        send_mail(
            f"{self.event.name}: {_('Ticket')} {ticket.get_code()}",
            render_to_string("events/emails/thank_you.html", {
                'event': self.event,
                'ticket': ticket,
                'is_waiting': ticket.status == Ticket.TicketStatus.WAITING
            }),
            settings.SERVER_EMAIL,
            [ticket.email]
        )

        self.type.tickets_remaining -= 1
        self.type.save()

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

        if self.ticket.status != Ticket.TicketStatus.READY_PAY_ON_SITE:
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
        self.ticket.status = Ticket.TicketStatus.CANCELLED
        self.ticket.save()

        messages.info(self.request, _("Ticket cancelled."))
        return redirect('event_index', self.event.slug)
