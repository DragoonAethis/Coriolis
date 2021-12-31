import uuid

from django.core.files.storage import default_storage

from PIL import Image, ImageOps

import events.models


def get_ticket_preview_path(instance: 'events.models.TicketType', filename):
    """Generates a new ticket preview path within MEDIA_ROOT."""
    return f"templates/{instance.event.slug}/{uuid.uuid4()}.png"


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
