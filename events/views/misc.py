import datetime
from typing import Tuple

from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.http import Http404

from payments import get_payment_model, RedirectNeeded, PaymentStatus
from payments_przelewy24.api import Przelewy24API

from events.models import Event, EventPage, Ticket, TicketType, Application, ApplicationType, Payment


def index(request):
    events = Event.objects.filter(active=True).order_by('date_from')

    if len(events) == 1:
        return redirect('event_index', slug=events[0].slug)

    return render(request, 'events/event_picker.html', {'events': events})


def event_index(request, slug):
    event = get_object_or_404(Event, slug=slug)

    now = datetime.datetime.now()
    context = {'event': event}

    if request.user.is_authenticated:
        context['tickets'] = Ticket.objects \
            .filter(event=event) \
            .filter(user=request.user) \
            .order_by('id')

        context['applications'] = Application.objects \
            .filter(event=event) \
            .filter(user=request.user) \
            .order_by('id')

        purchasable_ticket_types = TicketType.objects \
            .filter(event=event) \
            .filter(self_registration=True) \
            .filter(registration_to__gte=now) \
            .filter(registration_from__lte=now) \
            .filter(tickets_remaining__gt=0) \
            .count()

        context['can_purchase_tickets'] = purchasable_ticket_types > 0

        context['new_application_types'] = ApplicationType.objects \
            .filter(event=event) \
            .filter(registration_to__gte=now) \
            .filter(registration_from__lte=now)

    return render(request, 'events/index.html', context)


def event_page(request, slug, page_slug):
    event = get_object_or_404(Event, slug=slug)
    try:
        page = EventPage.objects.get(event=event, slug=page_slug)
    except EventPage.DoesNotExist:
        try:
            page = EventPage.objects.get(event=None, slug=page_slug)
        except EventPage.DoesNotExist:
            raise Http404('Page not found.')

    return render(request, 'events/events/page.html', context={
        'event': event,
        'page': page
    })


@login_required
def ticket_picker(request, slug):
    event = get_object_or_404(Event, slug=slug)
    now = datetime.datetime.now()

    types = TicketType.objects \
        .filter(event=event) \
        .filter(self_registration=True) \
        .filter(registration_to__gte=now) \
        .filter(registration_from__lte=now) \
        .order_by('id')

    if len(types) == 0:
        messages.add_message(request, messages.WARNING,
                             _("Online ticket sales for this event have ended. You can purchase a ticket on site."))
        return redirect('event_index', event.slug)

    return render(request, 'events/tickets/picker.html', {
        'event': event,
        'types': types,
    })


def get_event_and_ticket(slug, ticket_id) -> Tuple[Event, Ticket]:
    event = get_object_or_404(Event, slug=slug)
    ticket = get_object_or_404(Ticket, id=ticket_id)
    assert event.id == ticket.event_id
    return event, ticket


@login_required
def ticket_details(request, slug, ticket_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)

    if not ticket.user_id == request.user.id:
        messages.error(request, _("You don't own this ticket!"))
        return redirect('event_index', event.slug)

    return render(request, 'events/tickets/details.html', {
        'event': event,
        'ticket': ticket
    })


@login_required
def ticket_payment(request, slug, ticket_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)

    if not ticket.user_id == request.user.id:
        messages.error(request, _("You don't own this ticket!"))
        return redirect('event_index', event.slug)

    if ticket.status == Ticket.TicketStatus.READY_PAID:
        messages.success(request, _("This ticket was already paid for."))
        return redirect('event_index', event.slug)

    if not ticket.status == Ticket.TicketStatus.READY_PAY_ON_SITE:
        messages.error(request, _("You cannot pay for this ticket online."))
        return redirect('event_index', event.slug)

    if ticket.payment_set.count() > settings.PAYMENT_MAX_ATTEMPTS:
        messages.error(request, _("This ticket has too many payments in progress. Please contact the organizers."))
        return redirect('event_index', event.slug)

    payment = None
    for existing_payment in ticket.payment_set.all():
        # Can we restore any payment in progress?
        if existing_payment.status == PaymentStatus.CONFIRMED:
            # Forgot to update the status? Uh, okay...
            ticket.status = Ticket.TicketStatus.READY_PAID
            ticket.save()

            messages.success(request, _("This ticket was already paid for. Thank you!"))
            return redirect('event_index', event.slug)
        elif existing_payment.status in (PaymentStatus.WAITING, PaymentStatus.INPUT):
            payment = existing_payment

    if payment is None:  # Let's make a new one:
        payment = Payment(
            user=request.user,
            event=event,
            ticket=ticket,
            billing_email=request.user.email,
            billing_country_code=settings.PAYMENT_ISO_COUNTRY,

            variant=settings.PAYMENT_PAY_ONLINE_VARIANT,
            description=f"{ticket.code}: {ticket.name} ({ticket.type.name}, {ticket.event.name})",
            total=ticket.type.price.amount,
            currency=ticket.type.price.currency.code,
        )
        payment.save()

    try:
        form = payment.get_form(data=request.POST or None)
    except RedirectNeeded as redirect_to:
        return redirect(str(redirect_to))

    return render(request, 'events/tickets/payment.html', {
        'event': event,
        'ticket': ticket,
        'payment': payment,
        'form': form,
    })


@login_required
def ticket_payment_finalize(request, slug, ticket_id, payment_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)
    payment = get_object_or_404(Payment, id=payment_id)
    assert payment.ticket_id == ticket.id

    # TODO: REMOVE AWFUL HACK FOR PRZELEWY24
    # P24 sends us a notification after a successful payment. Unfortunately,
    # failures or rejections get radio silence - let's ask P24 what's up with
    # a given payment and update the status accordingly.
    if payment.variant == 'przelewy24' and payment.status == PaymentStatus.WAITING:
        p24_config = settings.PAYMENT_VARIANTS['przelewy24'][1]['config']
        p24_api = Przelewy24API(p24_config)
        response = p24_api.get_by_session_id(session_id=str(payment.id))
        print(response)  # i dunno lol

    if payment.status == PaymentStatus.CONFIRMED:
        messages.success(request, _("Payment successful - thank you!"))
        ticket.status = Ticket.TicketStatus.READY_PAID
    elif payment.status in (PaymentStatus.WAITING, PaymentStatus.INPUT):
        return redirect('ticket_payment', event.slug, ticket.id)
    elif payment.status == PaymentStatus.ERROR:
        messages.error(request, _("Payment failed on our end - please try again in a few minutes."))
    elif payment.status == PaymentStatus.REJECTED:
        messages.error(request, _("Payment rejected - please try again."))
    elif payment.status == PaymentStatus.REFUNDED:
        messages.warning(request, _("Payment refunded."))
        ticket.status = Ticket.TicketStatus.CANCELLED

    ticket.save()
    return redirect('ticket_details', event.slug, ticket.id)


@login_required
def application_details(request, slug, app_id):
    event = get_object_or_404(Event, slug=slug)
    application = get_object_or_404(Application, id=app_id)
    assert event.id == application.event_id

    if not application.user_id == request.user.id:
        messages.error(request, _("You don't own this application!"))
        return redirect('event_index', event.slug)

    return render(request, 'events/applications/application_details.html', {
        'event': event,
        'application': application
    })
