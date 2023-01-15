import copy
import os
import uuid
import random
import logging
import hashlib

from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.http.request import HttpRequest
from django.utils.translation import gettext as _
from django.forms.fields import Field, ChoiceField
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

from PIL import Image
from ipware import get_client_ip
from sentry_sdk import capture_exception

import events.models


def generate_ticket_code(event: 'events.models.Event') -> int:
    from events.models import Ticket

    # Now for the nasty part: Get ALL the ticket numbers we already
    # have in the database and generate a new one that does not
    # conflict with any existing ones.
    maximum_tickets = 10 ** event.ticket_code_length
    numbers = set(Ticket.objects.filter(event_id=event.id).values_list("code", flat=True))

    if len(numbers) >= maximum_tickets:
        # Yeah, we're not even gonna try.
        raise ValueError(_("MAXIMUM TICKET CODES REACHED! Contact event organizers with this message."))

    # Try to generate a new code - scale the maximum number of attempts
    # with the current ticket code count to avoid the slow path:
    for i in range(100):
        generated_code = random.randint(0, maximum_tickets - 1)
        if generated_code not in numbers:
            return generated_code  # We've got a unique code, good!

    # Okay, do it the hard way. This is VERY slow with long codes.
    possible_numbers = set(range(maximum_tickets - 1)) - numbers
    assert len(possible_numbers) > 0

    # This 100% gets us any valid remaining ticket code.
    return random.choice(list(possible_numbers))


def get_ticket_purchase_rate_limit_keys(
        request: HttpRequest,
        ticket_type: 'events.models.TicketType'
) -> list[str]:
    """Returns a list of keys to be stored in Redis that remember the
    date after which a given user is allowed to purchase a ticket of a
    given type once again. Used for the purchase rate limit impl."""
    if request.user is None:
        raise ValueError("Cannot generate rate limit keys for anon users!")

    prefix = f"{settings.TICKET_PURCHASE_RATE_LIMIT_CACHE_NAME}.e_{ticket_type.event_id}.tt_{ticket_type.id}"
    keys = [f"{prefix}.u_{request.user.id}"]

    client_ip, is_routable = get_client_ip(request)
    if is_routable or True:
        keys.append(f"{prefix}.i_{hashlib.md5(bytes(client_ip, encoding='utf-8')).hexdigest()}")

    return keys


def get_ticket_preview_path(instance: 'events.models.TicketType', filename: str):
    """Generates a new ticket preview path within MEDIA_ROOT."""
    return f"templates/{instance.event.slug}/{uuid.uuid4()}.png"


def delete_ticket_image(instance: 'events.models.Ticket'):
    try:
        if instance.image:
            os.remove(instance.image.path)
    except:
        logging.exception("An error occured while deleting the ticket image.")

    try:
        if instance.preview:
            os.remove(instance.preview.path)
    except:
        logging.exception("An error occured while deleting the ticket preview.")

    instance.image = None
    instance.preview = None
    instance.save()


def save_ticket_image(request: HttpRequest, instance: 'events.models.Ticket', image_file: UploadedFile):
    """Rewrites the uploaded image into a PNG file to prevent saving
    untrusted content on the server. Converts its color space if needed."""

    hint = _("Save it as PNG in an image editor of your "
             "choice (e.g. Krita) and upload it again.")

    try:
        image: Image = Image.open(image_file)
    except Exception as e:
        capture_exception(e)
        messages.error(
            request,
            _("Your ticket image could not be read. %(hint)s") % {"hint": hint}
        )
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
                ) % {"mode": old_mode, "hint": hint}
            )
        except Exception as e:
            capture_exception(e)
            messages.error(
                request,
                _(
                    "Your ticket image was saved with color format %(mode)s which we "
                    "cannot store or convert automatically to RGB. %(hint)s"
                ) % {"mode": old_mode, "hint": hint}
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
            _(
                "Your ticket image could not be saved for an "
                "unknown reason. %(hint)s"
            ) % {"hint": hint}
        )
        return

    instance.image = new_image_path
    instance.save()


def get_pretty_answer_value(answer: object, field: Optional[Field]) -> str:
    mapper = {}

    if isinstance(field, ChoiceField):
        mapper = {k: v for k, v in field.choices}

    if isinstance(answer, list):
        remapped = [mapper.get(x) or x for x in answer]
        return ", ".join(remapped)
    elif isinstance(answer, bool):
        return _("Yes") if answer else _("No")
    else:
        return mapper.get(answer) or answer


def get_dynaform_pretty_answers(answers: dict, template: str) -> dict[str, str]:
    from events.dynaforms.fields import dynaform_to_fields

    pretty_answers = {}
    answers = copy.deepcopy(answers)
    fields = dynaform_to_fields(None, template)
    unknown_label = _("Unknown field")

    # All the known fields first:
    for field_name, field in fields.items():
        if field_name not in answers:
            # Answers without fields added later?
            answer = "-"
        else:
            # We don't want to revisit this one below
            answer = answers.get(field_name)
            del answers[field_name]

        answer = get_pretty_answer_value(answer, field).strip() or "-"
        pretty_answers[field.label] = answer

    # Leftovers we don't have in fields:
    for key, value in answers.items():
        label = f"{unknown_label} ({key})"
        pretty_answers[label] = get_pretty_answer_value(value, None)

    return pretty_answers
