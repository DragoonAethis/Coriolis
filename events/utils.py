import os
import uuid
import random
import logging

from django.utils.translation import gettext as _
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

from PIL import Image, ImageOps

import events.models


def generate_ticket_code(event: 'events.models.Event') -> int:
    from events.models import Ticket

    # Now for the nasty part: Get ALL the ticket numbers we already
    # have in the database and generate a new one that does not
    # conflict with any existing ones.
    maximum_tickets = 10 ** event.ticket_code_length
    numbers = set(Ticket.objects.filter(event_id=event.id).values_list('code', flat=True))

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


def save_ticket_image(instance: 'events.models.Ticket', image_file: UploadedFile):
    image: Image = Image.open(image_file)

    new_image_path = f'ticketavatars/{instance.id}.png'
    with default_storage.open(new_image_path, 'wb') as handle:
        image.save(handle, 'png')

    instance.image = new_image_path
    generate_ticket_preview(instance)


def generate_ticket_preview(ticket: 'events.models.Ticket'):
    """Generates an identifier preview and saves it for later use."""
    if not ticket.image or not ticket.type.preview_image:
        return

    x, y, w, h = ticket.type.get_preview_box_coords()
    user_image: Image = Image.open(ticket.image.path)
    ticket_template: Image = Image.open(ticket.type.preview_image.path)
    preview: Image = Image.new(ticket_template.mode, ticket_template.size)

    resized_img = ImageOps.fit(user_image, (w, h), method=Image.BICUBIC)
    preview.paste(resized_img, box=(x, y, w, h))
    preview = Image.alpha_composite(preview, ticket_template)

    path = f'previews/{ticket.id}.png'
    with default_storage.open(path, 'wb') as handle:
        preview.save(handle, 'png')

    ticket.preview = path
    ticket.save()
