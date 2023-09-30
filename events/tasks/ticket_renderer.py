import os
import copy
import json
import shutil
import logging
import os.path
import tempfile
import subprocess
from typing import Optional

from django.conf import settings
from django.core.files.storage import default_storage

import dramatiq
from dramatiq.rate_limits import ConcurrentRateLimiter
from dramatiq.rate_limits.backends import RedisBackend

from events.models import Event, Ticket, TicketRenderer

RENDERER_MUTEX = ConcurrentRateLimiter(RedisBackend(), "ticket-renderer-mutex", limit=settings.TICKET_RENDERER_MAX_JOBS)


def get_container_tool() -> Optional[str]:
    for tool in ("podman", "docker"):
        if tool_path := shutil.which(tool):
            return tool_path

    return None


def render(renderer: TicketRenderer, render_path: str) -> Optional[str]:
    config = renderer.config
    if "image" not in config:
        raise ValueError("Container image name not found in the ticket " f"renderer configuration: {renderer}")

    arguments = [
        # fmt: off
        get_container_tool(),
        "run", "-i", "--rm",
        "--pull", "never",
        "-v", f"{render_path}:/render",
        "-w", "/render",
        "--network", "none",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--security-opt", "no-new-privileges:true",
        config["image"],
        # fmt: on
    ]

    # Let the job run for up to a minute:
    proc = subprocess.run(arguments, timeout=60)

    expected_image = os.path.join(render_path, "render.png")
    if proc.returncode != 0 or not os.path.exists(expected_image):
        logging.error(f"Renderer failure - code {proc.returncode} --- {proc.stdout} --- {proc.stderr}")
        return None

    return expected_image


def render_ticket_variant(data: dict, ticket: Ticket, variant: str, save_preview: bool):
    render_data = copy.deepcopy(data)
    requested_filename = f"{ticket.id}.{variant}.png"
    logging.info(f"Rendering ticket: {requested_filename}")

    user_image = None
    if ticket.image:
        user_image = "asset" + os.path.splitext(ticket.image.name)[-1]

    render_data["render"] = {
        "variant": variant,
        "image": user_image,
    }

    with tempfile.TemporaryDirectory() as td:
        render_json = os.path.join(td, "render.json")
        with open(render_json, "w") as f:
            json.dump(render_data, f)

        if user_image:
            asset_path = os.path.join(td, user_image)
            shutil.copy(ticket.image.file.name, asset_path)

        with RENDERER_MUTEX.acquire():
            image_path = render(ticket.event.ticket_renderer, td)

        if image_path is not None:
            with open(image_path, "rb") as f:
                wanted_path = os.path.join("previews", ticket.event.slug, requested_filename)
                actual_path = default_storage.save(wanted_path, f)

            if save_preview:
                ticket.preview = actual_path
                ticket.save()
        else:
            logging.warning(f"Render failed for {requested_filename}")


@dramatiq.actor(queue_name="ticket-renderer")
def render_ticket_variants(ticket_id: str, variants: Optional[list[str]] = None, save_preview: bool = True):
    """
    Generates multiple preview variants for a given ticket ID.

    ticket_id - ticket to generate the previews for.
    variants - a list of variants to generate (defaults to all known for the event)
    save_preview - whether to save the first generated preview to the ticket
    """
    if not get_container_tool():
        logging.error("Issued a render job with no render tools available.")

    try:
        ticket: Ticket = Ticket.objects.prefetch_related("user", "event", "type").get(id=ticket_id)
        event: Event = ticket.event
    except Ticket.DoesNotExist:
        logging.error(f"Issued a render job for missing ticket: {ticket_id}")
        return

    if not event.ticket_renderer or not event.ticket_renderer_variants:
        logging.error(
            f"Issued a render job on ticket ID {ticket_id}, " f"but event {event.name} is not configured for it."
        )
        return

    if variants is None:
        variants = []
        for v in event.ticket_renderer_variants.split(","):
            v = v.strip()
            if not v or v in variants:
                continue

            variants.append(v)

    render_metadata = {
        "render": {},  # To be filled by the variant renderer.
        "ticket": {
            "code": ticket.code,
            "prefixed_code": ticket.get_code(),
            "nickname": ticket.nickname,
            "age_gate": ticket.age_gate,
            "name": ticket.name,
            "email": ticket.email,
            "phone": str(ticket.phone),
        },
        "ticket_type": {
            "name": ticket.type.name,
            "color": ticket.type.color,
            "short_name": ticket.type.short_name or ticket.type.name,
            "code_prefix": ticket.type.code_prefix,
        },
        "event": {"name": ticket.event.name},
    }

    for variant in variants:
        render_ticket_variant(render_metadata, ticket, variant, save_preview)
        save_preview = False  # Save it just for the first generated one

    logging.info(f"Render finished for ticket: {ticket_id}")
