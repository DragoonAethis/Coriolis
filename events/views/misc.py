import datetime

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from payments import RedirectNeeded, PaymentStatus

from events.forms.registration import UpdateTicketForm
from events.models import Event, EventPage, Application, ApplicationType, Payment
from events.models.orgs import EventOrg
from events.models.tickets import Ticket, TicketType, TicketStatus


def index(request):
    events = Event.objects.filter(active=True).order_by("date_from")

    if len(events) == 1:
        return redirect("event_index", slug=events[0].slug)

    return render(request, "events/event_picker.html", {"events": events})


def event_index(request, slug):
    event = get_object_or_404(Event, slug=slug)

    now = datetime.datetime.now()
    context = {"event": event}

    if request.user.is_authenticated:
        # fmt: off
        # Black makes all this difficult to read :(

        user_tickets = (
            Ticket.objects.filter(event=event, user=request.user)
            .not_onsite()
            .order_by('id')
        )

        context["tickets"] = user_tickets
        context["valid_tickets"] = user_tickets.valid_statuses_only()

        context["applications"] = (
            Application.objects.filter(event=event)
            .filter(user=request.user)
            .order_by("id")
        )

        context["orgs"] = (
            EventOrg.objects.filter(event=event)
            .filter(owner=request.user)
            .prefetch_related("ticket_set")
            .order_by("name")
        )

        ticket_types = (
            TicketType.objects.filter(event=event)
            .filter(self_registration=True)
            .filter(tickets_remaining__gt=0)
        )

        purchasable_ticket_types = (
            ticket_types.filter(registration_to__gte=now)
            .filter(registration_from__lte=now)
            .count()
        )

        purchasable_in_future = (
            ticket_types.filter(registration_from__gt=now)
            .count()
        )

        context["can_purchase_tickets"] = purchasable_ticket_types > 0
        context["can_purchase_in_future"] = purchasable_in_future > 0

        context["new_application_types"] = (
            ApplicationType.objects.filter(event=event)
            .filter(registration_to__gte=now)
            .filter(registration_from__lte=now)
            .order_by("slug")
        )
        # fmt: on

    return render(request, "events/index.html", context)


def event_page(request, slug, page_slug):
    event = get_object_or_404(Event, slug=slug)
    try:
        page = EventPage.objects.get(event=event, slug=page_slug)
    except EventPage.DoesNotExist:
        try:
            page = EventPage.objects.get(event=None, slug=page_slug)
        except EventPage.DoesNotExist:
            raise Http404("Page not found.") from None

    return render(request, "events/events/page.html", context={"event": event, "event_page": page})


@login_required
def ticket_picker(request, slug):
    event = get_object_or_404(Event, slug=slug)
    now = datetime.datetime.now()

    types = (
        TicketType.objects.filter(event=event)
        .filter(self_registration=True)
        .filter(registration_to__gte=now)
        .filter(registration_from__lte=now)
        .order_by("display_order", "id")
    )

    if len(types) == 0:
        msg = _("Online ticket sales for this event have ended. You can purchase a ticket on site.")

        if event.sale_closed_notice:
            # This block may explicitly contain arbitrary HTML:
            msg = mark_safe(event.sale_closed_notice)  # noqa: S308

        messages.add_message(request, messages.WARNING, msg)
        return redirect("event_index", event.slug)

    return render(
        request,
        "events/tickets/picker.html",
        {
            "event": event,
            "types": types,
        },
    )


def get_event_and_ticket(slug, ticket_id) -> tuple[Event, Ticket]:
    event = get_object_or_404(Event, slug=slug)
    ticket = get_object_or_404(Ticket, id=ticket_id, event=event)
    return event, ticket


@login_required
def ticket_details(request, slug, ticket_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)

    if not ticket.user_id == request.user.id:
        if request.user.is_staff and request.user.has_perm("events.view_ticket"):
            messages.warning(request, _("This ticket is not yours!"))
        else:
            messages.error(request, _("You don't own this ticket!"))
            return redirect("event_index", event.slug)

    return render(
        request,
        "events/tickets/details.html",
        {
            "event": event,
            "ticket": ticket,
            "update_form": UpdateTicketForm(
                event=event,
                ticket=ticket,
                initial={
                    "nickname": ticket.nickname,
                    "shirt_size": ticket.shirt_size,
                },
            ),
        },
    )


def ticket_post_registration(request, slug, ticket_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)
    now = datetime.datetime.now()
    context = {
        "event": event,
        "ticket": ticket,
    }

    purchasables = (
        TicketType.objects.filter(event=event)
        .filter(self_registration=True)
        .filter(tickets_remaining__gt=0)
        .filter(registration_to__gte=now)
        .filter(registration_from__lte=now)
        .count()
    )

    context["can_purchase_tickets"] = purchasables > 0

    return render(request, "events/tickets/post_registration.html", context)


@login_required
def ticket_payment(request, slug, ticket_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)

    if not event.payment_enabled:
        # Nobody should get there in the first place, but...
        messages.error(request, "Payments temporarily disabled - sorry!")
        return redirect("event_index", event.slug)

    if not ticket.user_id == request.user.id:
        messages.error(request, _("You don't own this ticket!"))
        return redirect("event_index", event.slug)

    if ticket.paid:
        messages.success(request, _("This ticket was already paid for."))
        return redirect("event_index", event.slug)

    if not ticket.can_pay_online():
        messages.error(request, _("You cannot pay online for this ticket."))
        return redirect("event_index", event.slug)

    if ticket.type.special_payment_page:
        # Instead of running the standard payment flow, show the
        # special payment info page, adding the ticket code/title.
        content = ticket.type.special_payment_page.content
        replacements = [
            ("CORIOLIS_TICKET_PRICE", str(ticket.get_price())),
            ("CORIOLIS_TICKET_NAME", ticket.name),
            ("CORIOLIS_TICKET_CODE", ticket.get_code()),
        ]

        for token, replacement in replacements:
            content = content.replace(token, replacement)

        return render(
            request,
            "events/tickets/special_payment_page.html",
            {
                "event": event,
                "ticket": ticket,
                "content": content,
            },
        )

    if ticket.payment_set.count() >= settings.PAYMENT_MAX_ATTEMPTS:
        messages.error(
            request,
            _("This ticket has too many payments in progress. Please contact the organizers."),
        )
        return redirect("event_index", event.slug)

    payment = None
    resuming_payment_in_progress = False
    can_restore_payment_in_progress = True

    try:
        can_resume = int(request.GET.get("resume", "1"))
        can_restore_payment_in_progress = bool(can_resume)
    except ValueError:
        pass

    for existing_payment in ticket.payment_set.all():
        if existing_payment.status == PaymentStatus.CONFIRMED:
            messages.success(request, _("This ticket was already paid for. Thank you!"))
            return redirect("event_index", event.slug)

        # Can we restore any payment in progress?
        if (
            payment is None
            and can_restore_payment_in_progress
            and existing_payment.status in (PaymentStatus.WAITING, PaymentStatus.INPUT)
        ):
            # If multiple payments are eligible for resuming,
            # just use the last one on the list.
            payment = existing_payment
            resuming_payment_in_progress = True

    if payment is None:  # Let's make a new one:
        payment = Payment(
            user=request.user,
            event=event,
            ticket=ticket,
            billing_email=request.user.email,
            billing_country_code=settings.PAYMENT_ISO_COUNTRY,
            variant=settings.PAYMENT_PAY_ONLINE_VARIANT,
            description=f"{ticket.get_code()}: {ticket.name} ({ticket.type.name}, {ticket.event.name})",
            total=ticket.get_price().amount,
            currency=ticket.get_price().currency.code,
        )
        payment.save()

    try:
        form = payment.get_form(data=request.POST or None)
        form.helper = FormHelper()
        form.helper.form_action = form.action
        form.helper.form_method = form.method
        form.helper.add_input(Submit("submit", _("Continue Payment"), css_class="btn btn-lg btn-primary"))
    except RedirectNeeded as redirect_to:
        return redirect(str(redirect_to))

    if resuming_payment_in_progress:
        msg = format_html(
            '{} <a href="{}">{}</a>',
            _("Resuming an existing payment in progress. Problems?"),
            mark_safe(reverse("ticket_payment", args=[event.slug, ticket.id]) + "?resume=0"),  # noqa: S308
            _("Start a new payment."),
        )
        messages.info(request, msg)

    return render(
        request,
        "events/tickets/payment.html",
        {
            "event": event,
            "ticket": ticket,
            "payment": payment,
            "form": form,
        },
    )


@login_required
def ticket_payment_finalize(request, slug, ticket_id, payment_id):
    event, ticket = get_event_and_ticket(slug, ticket_id)
    payment = get_object_or_404(Payment, id=payment_id, ticket=ticket)

    if payment.status == PaymentStatus.WAITING:
        messages.warning(request, _("Still waiting for the payment confirmation - please try again in a few minutes."))
    elif payment.status == PaymentStatus.CONFIRMED:
        messages.success(request, _("Payment successful - thank you!"))
    elif payment.status in (PaymentStatus.WAITING, PaymentStatus.INPUT):
        return redirect("ticket_payment", event.slug, ticket.id)
    elif payment.status == PaymentStatus.ERROR:
        messages.error(request, _("Payment failed on our end - please try again in a few minutes."))
    elif payment.status == PaymentStatus.REJECTED:
        messages.error(request, _("Payment rejected - please try again."))
    elif payment.status == PaymentStatus.REFUNDED:
        messages.warning(request, _("Payment refunded."))
        ticket.status = TicketStatus.CANCELLED
        ticket.save()

    return redirect("ticket_details", event.slug, ticket.id)
