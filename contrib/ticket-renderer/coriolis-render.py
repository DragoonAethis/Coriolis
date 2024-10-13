import json
import os

from jinja2 import Environment, select_autoescape
from playwright.sync_api import sync_playwright

TICKET_WIDTH = int(os.environ["TICKET_WIDTH"])
TICKET_HEIGHT = int(os.environ["TICKET_HEIGHT"])

TICKET_CROP_X = int(os.environ.get("TICKET_CROP_X", 0))
TICKET_CROP_Y = int(os.environ.get("TICKET_CROP_Y", 0))
TICKET_CROP_W = int(os.environ.get("TICKET_CROP_W", TICKET_WIDTH))
TICKET_CROP_H = int(os.environ.get("TICKET_CROP_H", TICKET_HEIGHT))

with open("render.html.j2") as f:
    env = Environment(autoescape=select_autoescape())
    template = env.from_string(f.read())

with open("render.json") as f:
    template_params = json.load(f)

with open("render.html", "w") as f:
    f.write(template.render(template_params))

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_viewport_size(
        {
            "width": TICKET_WIDTH,
            "height": TICKET_HEIGHT,
        }
    )

    page.goto(f"file://{os.getcwd()}/render.html", wait_until="load")

    # For whatever reason, the screenshot might be taken before
    # Chromium finishes the page paint, which usually results in
    # the bottom text randomly disappearing. Retaking the same
    # screenshot in the same environment fixes it, every time.
    # Miss rate seems to be around 15%.
    #
    # Wait for 100ms here just to make sure the paint finishes.
    # This should not happen, but I don't have any better ideas.
    page.wait_for_timeout(100)

    page.screenshot(
        path="render.png",
        clip={
            "x": TICKET_CROP_X,
            "y": TICKET_CROP_Y,
            "width":  TICKET_CROP_W,
            "height": TICKET_CROP_H,
        },
    )

    browser.close()
