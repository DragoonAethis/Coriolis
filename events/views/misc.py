import datetime

from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from events.models import Event, EventPage, Ticket, TicketType, Application, ApplicationType


def index(request):
    events = Event.objects.filter(active=True).order_by('date_from')

    if len(events) == 1:
        return redirect('event_index', slug=events[0].slug)

    return render(request, 'events/event_picker.html', {'events': events})


def event_index(request, slug):
    event = get_object_or_404(Event, slug=slug)

    now = datetime.datetime.utcnow()
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
    page = get_object_or_404(EventPage, event=event, slug=page_slug)

    return render(request, 'events/events/page.html', context={
        'event': event,
        'page': page
    })


@login_required
def ticket_details(request, slug, id):
    event = get_object_or_404(Event, slug=slug)
    ticket = get_object_or_404(Ticket, id=id)
    assert event.id == ticket.event_id

    if not ticket.user_id == request.user.id:
        messages.error(request, _("You don't own this ticket!"))
        return redirect('event_index', event.slug)

    return render(request, 'events/tickets/details.html', {
        'event': event,
        'ticket': ticket
    })


@login_required
def application_details(request, slug, id):
    event = get_object_or_404(Event, slug=slug)
    application = get_object_or_404(Application, id=id)
    assert event.id == application.event_id

    if not application.user_id == request.user.id:
        messages.error(request, _("You don't own this application!"))
        return redirect('event_index', event.slug)

    return render(request, 'events/applications/application_details.html', {
        'event': event,
        'application': application
    })


@login_required
def ticket_picker(request, slug):
    event = get_object_or_404(Event, slug=slug)
    now = datetime.datetime.utcnow()

    types = TicketType.objects \
        .filter(event=event) \
        .filter(self_registration=True) \
        .filter(registration_to__gte=now) \
        .filter(registration_from__lte=now) \
        .filter(tickets_remaining__gt=0)

    if len(types) == 0:
        messages.add_message(request, messages.WARNING,
                             _("Online ticket sales for this event have ended. You can purchase a ticket on site."))
        return redirect('event_index', event.slug)

    return render(request, 'events/tickets/picker.html', {
        'event': event,
        'types': types,
    })
