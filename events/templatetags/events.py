from django import template
from django.conf import settings
from django.contrib.messages import DEBUG, INFO, SUCCESS, WARNING, ERROR
from django.forms import BaseForm
from django.forms.widgets import PasswordInput
from django.template import RequestContext
from django.utils.html import mark_safe

import xml.etree.ElementTree as etree

from markdown import markdown
from markdown.extensions.tables import TableExtension, TableProcessor

register = template.Library()

MESSAGE_LEVEL_TO_CSS_CLASS = {
    INFO: "primary",
    SUCCESS: "success",
    WARNING: "warning",
    ERROR: "danger",
    DEBUG: "secondary",
}


class CustomTableProcessor(TableProcessor):
    def run(self, parent: etree.Element, blocks: list[str]) -> None:
        super().run(parent, blocks)
        if len(parent) > 0 and parent[-1].tag == "table":
            table = parent[-1]
            table.attrib["class"] = "table table-bordered table-striped table-hover"


class CustomTableExtension(TableExtension):
    def extendMarkdown(self, md):
        """ Add an instance of `CustomTableProcessor` to `BlockParser`. """
        if '|' not in md.ESCAPED_CHARS:
            md.ESCAPED_CHARS.append('|')
        processor = CustomTableProcessor(md.parser, self.getConfigs())
        md.parser.blockprocessors.register(processor, 'table', 75)


@register.simple_tag
def level_to_bootstrap_css_class(level: int) -> str:
    return MESSAGE_LEVEL_TO_CSS_CLASS.get(level) or "primary"


@register.simple_tag
def render_markdown(content: str, strip_wrapper: bool = False) -> str:
    text = markdown(content, output_format="html", extensions=[
        "abbr",
        "attr_list",
        "def_list",
        "fenced_code",
        "footnotes",
        "md_in_html",
        CustomTableExtension(),
    ]).strip()

    # A quick and somewhat hacky way to strip the wrapping
    # <p> element, but only if there's a single <p> in the text.
    # This is not fully compliant, but much faster than building
    # the full HTML tree, then serializing it back to text.
    if (
            strip_wrapper
            and text.startswith("<p>")
            and text.endswith("</p>")
            and text.find("</p>") == text.rfind("</p>")
    ):
        text = text[3:-4]

    # Disable Ruff warnings about mark_safe, since we're explicitly building HTML here:
    return mark_safe(text)  # noqa: S308


@register.simple_tag(takes_context=True)
def get_body_css_classes(context: RequestContext) -> str:
    from events.models.events import Event

    classes = [
        f"environment-{settings.ENVIRONMENT}",
        f"logged-{'in' if context.request.user.is_authenticated else 'out'}",
    ]

    event: Event | None = context.get("event")
    if event is not None:
        classes.append(f"event-{event.slug}")  # noqa

    if settings.DEBUG:
        classes.append("debug-enabled")

    return " ".join(classes)


@register.simple_tag(takes_context=True)
def get_counter_bg_class(context: RequestContext, value: int, expected_value: int):
    if value < expected_value:
        return "danger"
    elif value == expected_value:
        return "success"
    else:
        return "warning"


@register.filter
def allauth_autocomplete(form: BaseForm) -> BaseForm:
    """
    django-allauth forms containing passwords set autocomplete='new-password'
    on the first field, but not on the second. Force set the autocomplete value
    on those to make Chrome/KeePass password generators work well.
    """

    if "password2" in form.fields:
        widget: PasswordInput = form.fields["password2"].widget
        widget.attrs["autocomplete"] = "new-password"

    return form
