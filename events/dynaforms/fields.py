from abc import ABC
from typing import Literal, Optional, Union, ClassVar, Annotated

import markdown
from django.forms.fields import Field
from django.forms.widgets import Widget
from django.forms import fields, widgets
from django.utils.safestring import mark_safe
from phonenumber_field import formfields as pnfields

from pydantic import validator, BaseModel, Field as PydanticField


class DynaformField(BaseModel, ABC):
    kind: Literal[None]
    _field_class: ClassVar[Field] = None
    _widget: ClassVar[Widget] = None

    label: str
    label_type: str = "text"

    help_text: Optional[str] = None
    help_text_type: str = "text"

    required: bool = True


class ChoiceField(DynaformField, ABC):
    choices: dict[str, str]

    @validator("choices")
    def must_have_any_choices(cls, v):
        if len(v) == 0:
            raise ValueError("must have any choices")
        return v


class CharField(DynaformField):
    kind: Literal["char"]
    _field_class: ClassVar[Field] = fields.CharField


class TextField(DynaformField):
    kind: Literal["text"]
    _field_class: ClassVar[Field] = fields.CharField
    _widget = widgets.Textarea


class EmailField(DynaformField):
    kind: Literal["email"]
    _field_class: ClassVar[Field] = fields.EmailField


class PhoneNumberField(DynaformField):
    kind: Literal["phone"]
    _field_class: ClassVar[Field] = pnfields.PhoneNumberField


class BooleanField(DynaformField):
    kind: Literal["checkbox"]
    _field_class: ClassVar[Field] = fields.BooleanField


class SelectField(ChoiceField):
    kind: Literal["select"]
    _field_class: ClassVar[Field] = fields.ChoiceField
    _widget: ClassVar[Widget] = widgets.Select


class MultiSelectField(ChoiceField):
    kind: Literal["multiselect"]
    _field_class: ClassVar[Field] = fields.MultipleChoiceField
    _widget: ClassVar[Widget] = widgets.SelectMultiple


class RadioField(ChoiceField):
    kind: Literal["radio"]
    _field_class: ClassVar[Field] = fields.ChoiceField
    _widget: ClassVar[Widget] = widgets.RadioSelect


class CheckboxField(ChoiceField):
    kind: Literal["multicheckbox"]
    _field_class: ClassVar[Field] = fields.MultipleChoiceField
    _widget: ClassVar[Widget] = widgets.CheckboxSelectMultiple


DynaformFieldUnion = Annotated[
    Union[
        CharField,
        TextField,
        EmailField,
        PhoneNumberField,
        BooleanField,
        SelectField,
        MultiSelectField,
        RadioField,
        CheckboxField,
    ],
    PydanticField(discriminator="kind"),
]


class DynaformFieldConfiguration(BaseModel):
    fields: dict[str, DynaformFieldUnion]


def transform_choices(choices) -> list[(str, str)]:
    return [(k, v) for k, v in choices.items()]


def dynaform_prefix(name: Optional[str]) -> str:
    if name:
        return f"df__{name}__"
    else:
        return ""


def parse_text_type_transform(config: dict, text_key: str, type_key: str) -> None:
    if not (text_type := config.get(type_key)):
        return

    # We should not pass this to the field constructor:
    del config[type_key]

    if not (text := config.get(text_key)):
        return

    if text_type == "text":
        pass
    elif text_type == "html":
        text = mark_safe(text)
    elif text_type == "markdown":
        rendered = markdown.markdown(text, output_format="html5")

        # A quick and somwhat hacky way to strip the wrapping
        # <p> element, but only if there's a single <p> in the text.
        # This is not fully compliant, but much faster than building
        # the full HTML tree, then serializing it back to text.
        if text.find("</p>") == text.rfind("</p>"):
            rendered = rendered.removeprefix("<p>").removesuffix("</p>")

        text = mark_safe(rendered)
    else:
        raise ValueError(f"{type_key} is not one of text/html/markdown!")

    config[text_key] = text


def dynaform_to_fields(name: Optional[str], template: str) -> dict[str, Field]:
    config = DynaformFieldConfiguration.parse_raw(template)
    prefix = dynaform_prefix(name)
    dynamic_fields = {}

    field_config: DynaformField
    for field_name, field_config in config.fields.items():
        config_args = field_config.dict()

        if "kind" in config_args:
            del config_args["kind"]

        if field_config._widget is not None:
            config_args["widget"] = field_config._widget

        if "choices" in config_args:
            config_args["choices"] = transform_choices(config_args["choices"])

        parse_text_type_transform(config_args, "label", "label_type")
        parse_text_type_transform(config_args, "help_text", "help_text_type")

        dynamic_fields[prefix + field_name] = field_config._field_class(**config_args)

    return dynamic_fields
