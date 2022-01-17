import os
import uuid
import logging

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

from PIL import Image, ImageOps

import events.models


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
