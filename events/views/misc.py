import datetime
from typing import Tuple

import django.http.response
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.conf import settings
from django.http import Http404

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from payments import RedirectNeeded, PaymentStatus
from payments_przelewy24.api import Przelewy24API

from events.models import Event, EventPage, Ticket, TicketType, TicketStatus, Application, ApplicationType, Payment
from events.models.tickets import VaccinationProof
from events.forms import UpdateTicketForm


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


def prometheus_status(request, slug, key):
    event = get_object_or_404(Event, slug=slug)
    if not event.prometheus_key or key != event.prometheus_key:
        return django.http.response.HttpResponseForbidden("yeet the ayyyys")

    counters = [
        ('tickets_ready_pay_on_site',
         'Number of tickets registered, but not paid for.',
         lambda x: x[0] == TicketStatus.READY_PAY_ON_SITE),
        ('tickets_ready_paid',
         'Number of tickets paid for before the event.',
         lambda x: x[0] == TicketStatus.READY_PAID),
        ('tickets_used',
         'Number of used tickets.',
         lambda x: x[0] == TicketStatus.USED),
        ('vaccination_proof_none',
         'Number of used tickets for which we have no vaccination proof.',
         lambda x: x[0] == TicketStatus.USED and x[1] == VaccinationProof.NONE),
        ('vaccination_proof_weak',
         'Number of used tickets for which we have a weak vaccination proof.',
         lambda x: x[0] == TicketStatus.USED and x[1] == VaccinationProof.WEAK),
        ('vaccination_proof_strong',
         'Number of used tickets for which we have a strong vaccination proof.',
         lambda x: x[0] == TicketStatus.USED and x[1] == VaccinationProof.STRONG)
    ]

    data = Ticket.objects\
        .filter(event_id=event.id)\
        .filter(status__in=(TicketStatus.READY_PAY_ON_SITE, TicketStatus.READY_PAID, TicketStatus.USED))\
        .values_list('status', 'vaccination_proof')

    output_metrics = []

    for counter in counters:
        value = 0
        for sample in data:
            if counter[2](sample):
                value += 1

        output_metrics.extend([
            f"# HELP {counter[0]} {counter[1]}",
            f"# TYPE {counter[0]} counter",
            f"{counter[0]} {value}"
        ])

    output_metrics.append('')
    return django.http.response.HttpResponse("\n".join(output_metrics))


@login_required
def ticket_picker(request, slug):
    event = get_object_or_404(Event, slug=slug)
    now = datetime.datetime.now()

    types = TicketType.objects \
        .filter(event=event) \
        .filter(self_registration=True) \
        .filter(registration_to__gte=now) \
        .filter(registration_from__lte=now) \
        .order_by('display_order', 'id')

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
        'ticket': ticket,
        'update_form': UpdateTicketForm(event=event, ticket=ticket, initial={
            'nickname': ticket.nickname
        })
    })


@login_required
def ticket_payment(request, slug, ticket_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)

    if not event.payment_enabled:
        # Nobody should get there in the first place, but...
        messages.error(request, "Payments temporarily disabled - sorry!")
        return redirect('event_index', event.slug)

    if not ticket.user_id == request.user.id:
        messages.error(request, _("You don't own this ticket!"))
        return redirect('event_index', event.slug)

    if ticket.status == TicketStatus.READY_PAID:
        messages.success(request, _("This ticket was already paid for."))
        return redirect('event_index', event.slug)

    if not ticket.can_pay_online():
        messages.error(request, _("You cannot pay online for this ticket."))
        return redirect('event_index', event.slug)

    if ticket.payment_set.count() >= settings.PAYMENT_MAX_ATTEMPTS:
        messages.error(request, _("This ticket has too many payments in progress. Please contact the organizers."))
        return redirect('event_index', event.slug)

    payment = None
    can_restore_payment_in_progress = True
    try:
        can_resume = int(request.GET.get('resume', '1'))
        can_restore_payment_in_progress = bool(can_resume)
    except ValueError:
        pass

    for existing_payment in ticket.payment_set.all():
        if existing_payment.status == PaymentStatus.CONFIRMED:
            # Forgot to update the status? Uh, okay...
            ticket.status = TicketStatus.READY_PAID
            ticket.paid = True
            ticket.save()

            messages.success(request, _("This ticket was already paid for. Thank you!"))
            return redirect('event_index', event.slug)

        # Can we restore any payment in progress?
        if (payment is None
            and can_restore_payment_in_progress
            and existing_payment.status in (PaymentStatus.WAITING, PaymentStatus.INPUT)
        ):
            payment = existing_payment
            resuming_message = _("Resuming an existing payment in progress. Problems?")
            no_resuming_link_label = _("Start a new payment.")
            no_resuming_link = reverse('ticket_payment', args=[event.slug, ticket.id]) + '?resume=0'
            msg = mark_safe(f'{resuming_message} <a href="{no_resuming_link}">{no_resuming_link_label}</a>')
            messages.info(request, msg)

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
        form.helper = FormHelper()
        form.helper.form_action = form.action
        form.helper.form_method = form.method
        form.helper.add_input(Submit('submit', _('Continue Payment'), css_class="btn btn-lg btn-primary"))
    except RedirectNeeded as redirect_to:
        return redirect(str(redirect_to))

    return render(request, 'events/tickets/payment.html', {
        'event': event,
        'ticket': ticket,
        'payment': payment,
        'form': form,
    })


def request_przelewy24_transaction_info(request, payment):
    # P24 sends us a notification after a successful payment. Unfortunately,
    # failures or rejections get radio silence - let's ask P24 what's up with
    # a given payment and update the status accordingly.

    p24_config = settings.PAYMENT_VARIANTS['przelewy24'][1]['config']
    p24_api = Przelewy24API(p24_config)
    response = p24_api.get_by_session_id(session_id=str(payment.id))
    if 'data' not in response or 'status' not in response['data']:
        return

    status = response['data']['status']
    if status == 0:
        messages.warning(request, _("We did not receive a payment notification from Przelewy24. "
                                    "Try again later or contact organizers about this issue."))
    elif status == 3:
        payment.status = PaymentStatus.REFUNDED
        payment.save()


@login_required
def ticket_payment_finalize(request, slug, ticket_id, payment_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)
    payment = get_object_or_404(Payment, id=payment_id)
    assert payment.ticket_id == ticket.id

    # TODO: REMOVE AWFUL HACK FOR PRZELEWY24
    if payment.variant == 'przelewy24' and payment.status == PaymentStatus.WAITING:
        request_przelewy24_transaction_info(request, payment)

    if payment.status == PaymentStatus.CONFIRMED:
        messages.success(request, _("Payment successful - thank you!"))
        ticket.status = TicketStatus.READY_PAID
        ticket.paid = True
    elif payment.status in (PaymentStatus.WAITING, PaymentStatus.INPUT):
        return redirect('ticket_payment', event.slug, ticket.id)
    elif payment.status == PaymentStatus.ERROR:
        messages.error(request, _("Payment failed on our end - please try again in a few minutes."))
    elif payment.status == PaymentStatus.REJECTED:
        messages.error(request, _("Payment rejected - please try again."))
    elif payment.status == PaymentStatus.REFUNDED:
        messages.warning(request, _("Payment refunded."))
        ticket.status = TicketStatus.CANCELLED

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
