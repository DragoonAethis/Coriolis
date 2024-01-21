import copy
from typing import Literal

from django.forms.fields import Field, ChoiceField
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from events.templatetags.events import render_markdown

TextFormats = Literal["text", "html", "markdown"]


def transform_text(text: str, text_type: TextFormats) -> str:
    if text_type == "text":
        return text
    elif text_type == "html":
        return mark_safe(text)  # noqa: S308
    elif text_type == "markdown":
        return render_markdown(text)
    else:
        raise ValueError(f"Text type '{text_type}' is not one of text/html/markdown!")


def parse_text_type_transform(config: dict, text_key: str, type_key: str) -> None:
    text: str
    text_type: TextFormats

    if not (text_type := config.get(type_key)):
        return

    # We should not pass this to the field constructor:
    del config[type_key]

    if not (text := config.get(text_key)):
        return

    config[text_key] = transform_text(text, text_type)


def get_pretty_answer_value(answer: object, field: Field | None) -> str:
    mapper = {}

    if isinstance(field, ChoiceField):
        mapper = dict(field.choices)

    if isinstance(answer, list):
        remapped = [mapper.get(x) or x for x in answer]
        return ", ".join(remapped)
    elif isinstance(answer, bool):
        return _("Yes") if answer else _("No")
    else:
        return str(mapper.get(answer) or answer)


def get_pretty_answers(answers: dict, fields: dict[str, Field]) -> dict[str, str]:
    pretty_answers = {}
    answers = copy.deepcopy(answers)
    unknown_label = _("Unknown field")

    # All the known fields first:
    for field_name, field in fields.items():
        try:
            # We don't want to revisit this one below
            value = answers.pop(field_name)
            answer = get_pretty_answer_value(value, field).strip() or "-"
        except KeyError:
            # Answers without fields added later?
            answer = "-"

        pretty_answers[field.label] = answer

    # Leftovers we don't have in fields:
    for key, value in answers.items():
        label = f"{unknown_label} ({key})"
        pretty_answers[label] = get_pretty_answer_value(value, None)

    return pretty_answers
