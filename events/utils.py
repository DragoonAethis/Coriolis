import hashlib
import logging
import os
import random
from decimal import Decimal

from PIL import Image
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import validate_email
from django.http.request import HttpRequest
from django.utils.translation import gettext as _
from ipware import get_client_ip
from sentry_sdk import capture_exception

import events.models


def check_event_perms(request, event: "events.models.Event", perms: list[str]) -> None:
    """Returns an appropriate redirect if the crew permission check fails."""
    _ = event  # noqa
    if not (request.user.is_staff and request.user.has_perms(perms)):
        raise PermissionDenied


def validate_multiple_emails(value: str):
    """Checks if the provided string is a comma-separated list of valid emails."""
    value = value.strip()
    if not value:
        return  # Valid, but nothing to check

    for mail in value.split(","):
        validate_email(mail.strip())


def generate_ticket_codes(event: "events.model.Event", how_many: int) -> list[int]:
    from events.models import Ticket

    # Now for the nasty part: Get ALL the ticket numbers we already
    # have in the database and generate a new one that does not
    # conflict with any existing ones.
    maximum_tickets = 10 ** event.ticket_code_length
    existing_codes = set(Ticket.objects.filter(event_id=event.id).values_list("code", flat=True))

    if len(existing_codes) >= maximum_tickets:
        # Yeah, we're not even gonna try.
        raise ValueError(_("MAXIMUM TICKET CODES REACHED! Contact event organizers with this message."))

    # Okay, do it the hard way. This is VERY slow with long codes.
    possible_numbers = set(range(maximum_tickets - 1)) - existing_codes
    if len(possible_numbers) < how_many:
        raise ValueError(_("MAXIMUM TICKET CODES REACHED! Contact event organizers with this message."))

    # This 100% gets us any valid remaining ticket code.
    return random.sample(sorted(possible_numbers), how_many)  # noqa: S311


def generate_ticket_code(event: "events.models.Event") -> int:
    return generate_ticket_codes(event, 1)[0]


def get_ticket_purchase_rate_limit_keys(request: HttpRequest, ticket_type: "events.models.TicketType") -> list[str]:
    """Returns a list of keys to be stored in Redis that remember the
    date after which a given user is allowed to purchase a ticket of a
    given type once again. Used for the purchase rate limit impl."""
    if request.user is None:
        raise ValueError("Cannot generate rate limit keys for anon users!")

    prefix = f"{settings.TICKET_PURCHASE_RATE_LIMIT_CACHE_NAME}.e_{ticket_type.event_id}.tt_{ticket_type.id}"
    keys = [f"{prefix}.u_{request.user.id}"]

    client_ip, is_routable = get_client_ip(request)
    if is_routable or True:
        # We don't want to directly store the IP address as the key in Redis:
        keys.append(f"{prefix}.i_{hashlib.md5(bytes(client_ip, encoding='utf-8')).hexdigest()}")  # noqa: S324

    return keys


def get_ticket_preview_path(instance: "events.models.TicketType", filename: str):
    """This function is deprecated but kept for migration backwards compatibility."""
    return "/tmp/DEPRECATED-DO-NOT-USE"  # noqa: S108


def delete_ticket_image(instance: "events.models.Ticket"):
    try:
        if instance.image:
            os.remove(instance.image.path)
    except:  # noqa
        logging.exception("An error occurred while deleting the ticket image.")

    try:
        if instance.preview:
            os.remove(instance.preview.path)
    except:  # noqa
        logging.exception("An error occurred while deleting the ticket preview.")

    instance.image = None
    instance.preview = None
    instance.save()


def save_ticket_image(request: HttpRequest, instance: "events.models.Ticket", image_file: UploadedFile):
    """Rewrites the uploaded image into a PNG file to prevent saving
    untrusted content on the server. Converts its color space if needed."""

    hint = _("Save it as PNG in an image editor of your choice (e.g. Krita) and upload it again.")

    try:
        image: Image = Image.open(image_file)
    except Exception as e:
        capture_exception(e)
        messages.error(request, _("Your ticket image could not be read. %(hint)s") % {"hint": hint})
        return

    if image.mode not in ("1", "L", "LA", "I", "P", "RGB", "RGBA"):
        old_mode = image.mode
        try:
            image = image.convert("RGB")
            messages.warning(
                request,
                _(
                    "Your ticket image was saved with color format %(mode)s which we "
                    "cannot store. It was converted to RGB and may not look correct. %(hint)s"
                )
                % {"mode": old_mode, "hint": hint},
            )
        except Exception as e:
            capture_exception(e)
            messages.error(
                request,
                _(
                    "Your ticket image was saved with color format %(mode)s which we "
                    "cannot store or convert automatically to RGB. %(hint)s"
                )
                % {"mode": old_mode, "hint": hint},
            )
            return

    try:
        new_image_path = f"ticketavatars/{instance.id}.png"
        with default_storage.open(new_image_path, "wb") as handle:
            image.save(handle, "png")
    except Exception as e:
        capture_exception(e)
        messages.error(
            request,
            _("Your ticket image could not be saved for an unknown reason. %(hint)s") % {"hint": hint},
        )
        return

    instance.image = new_image_path
    instance.save()


def generate_bulk_refunds(
        event: "events.models.Event",
        ticket_types: "tuple[events.models.TicketType | int]",
        statuses: tuple[str] = ("OKNP", "USED"),
        target_refund_amount: Decimal | None = None,
        title: str | None = None,
):
    from events.models import Ticket, RefundRequest

    tickets = Ticket.objects.filter(
        event=event,
        type_id__in=set(i if isinstance(i, int) else i.id for i in ticket_types),
        status__in=statuses,
        contributed_value__gt=0
    ).prefetch_related("payment_set")

    print(f"Tickets to refund: {len(tickets)}")
    created_refunds = []
    faulty_tickets = []

    for ticket in tickets:
        # Determine the best payment for a ticket:
        best_payment = None
        for payment in ticket.payment_set.all():
            if payment.status != 'confirmed':
                continue

            if best_payment is None:
                best_payment = payment

            if payment.captured_amount > best_payment.captured_amount:
                best_payment = payment

        if best_payment is None:
            logging.error(f"[{ticket.id}] Ticket is missing a valid target payment to refund!")
            faulty_tickets.append(ticket)
            continue

        refund_amount = target_refund_amount
        if refund_amount is None:
            refund_amount = ticket.contributed_value.amount

        if refund_amount > ticket.contributed_value.amount:
            logging.error(f"[{ticket.id}] Ticket has lower total contributed value than the requested refund!")
            faulty_tickets.append(ticket)
            continue

        if refund_amount > best_payment.captured_amount:
            logging.error(f"[{ticket.id}] Determined best payment {best_payment.id} has lower captured amount than the requested refund!")
            faulty_tickets.append(ticket)
            continue

        rr = RefundRequest(
            approved=True,
            payment=best_payment,
            amount=refund_amount,
            title=title,
        )

        created_refunds.append(rr)

    print(f"About to create {len(created_refunds)} refunds...")
    RefundRequest.objects.bulk_create(created_refunds)

    print(f"Faulty tickets:")
    for t in faulty_tickets:
        print(f"{t.id};{t.get_code()};{t.name};{t.contributed_value}")
