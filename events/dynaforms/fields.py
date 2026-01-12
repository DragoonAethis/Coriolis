import re
from abc import ABC
from typing import Literal, Union, Annotated

import pydantic
from crispy_forms.layout import LayoutObject, HTML, Field
from django.forms import fields, widgets
from django.forms.widgets import Widget
from phonenumber_field import formfields as pnfields
from pydantic import field_validator, BaseModel, Field as PydanticField

from events.dynaforms.utils import (
    translate_text,
    parse_text_type_transform,
    parse_translation_transform,
)
from events.templatetags.events import render_markdown

type LocalizableLabel = str | dict[str, str]

SIMPLE_IDENTIFIER_PATTERN = r"^[a-zA-Z0-9_-]+$"


class DynaformNode(BaseModel, ABC):
    kind: Literal[None]
    _field_class: type[Field] | None = None
    _widget: type[Widget] | None = None

    def is_form_field(self):
        """Determines if a node is a form field. True for things like
        text inputs or checkboxes, False for things like headers and images."""
        return self._field_class is not None

    def get_field(self, name: str) -> Field | None:
        if self._field_class is None:
            return None

        raise NotImplementedError(f"Override this method for {type(self)}!")

    def get_layout_object(self, name: str) -> LayoutObject | None:
        if self._field_class is None:
            return None

        raise NotImplementedError(f"Override this method for {type(self)}!")


class DynaformTemplate(DynaformNode):
    kind: Literal["template"]

    content: LocalizableLabel
    content_type: Literal["markdown", "html"] = "html"

    def get_layout_object(self, name: str) -> HTML:
        content = self.content

        if isinstance(content, dict):
            content = translate_text(content)

        if self.content_type == "markdown":
            content = render_markdown(content, strip_wrapper=True)

        return HTML(content)


class DynaformField(DynaformNode, ABC):
    label: LocalizableLabel
    label_type: Literal["text", "markdown", "html"] = "text"

    help_text: LocalizableLabel | None = None
    help_text_type: Literal["text", "markdown", "html"] = "text"

    required: bool = True

    def get_field_class_args(self) -> dict:
        args = self.model_dump(exclude_none=True)

        if "kind" in args:
            del args["kind"]

        if self._widget is not None:
            args["widget"] = self._widget

        parse_translation_transform(args, "label")
        parse_translation_transform(args, "help_text")

        parse_text_type_transform(args, "label", "label_type")
        parse_text_type_transform(args, "help_text", "help_text_type")

        return args

    def get_field(self, name: str) -> Field | None:
        if self._field_class is None:
            return None

        return self._field_class(**self.get_field_class_args())

    def get_layout_object(self, name: str) -> LayoutObject | None:
        if self._field_class is None:
            return None

        return Field(name)


class CharField(DynaformField):
    kind: Literal["char"]
    _field_class: type[Field] = fields.CharField


class TextField(DynaformField):
    kind: Literal["text"]
    _field_class: type[Field] = fields.CharField
    _widget = widgets.Textarea


class URLField(DynaformField):
    kind: Literal["url"]
    _field_class: type[Field] = fields.URLField


class EmailField(DynaformField):
    kind: Literal["email"]
    _field_class: type[Field] = fields.EmailField


class PhoneNumberField(DynaformField):
    kind: Literal["phone"]
    _field_class: type[Field] = pnfields.PhoneNumberField


class BooleanField(DynaformField):
    kind: Literal["checkbox"]
    _field_class: type[Field] = fields.BooleanField


class CounterField(DynaformField):
    kind: Literal["counter"]
    _field_class: type[Field] = fields.IntegerField

    initial: int = 0
    min_value: int | None = None
    max_value: int | None = None

    def get_field_class_args(self) -> dict:
        args = super().get_field_class_args()
        return args

    def get_layout_object(self, name: str) -> LayoutObject | None:
        return Field(name, template="events/dynaforms/counter_field.html")


class ChoiceField(DynaformField, ABC):
    choices: dict[str, LocalizableLabel]

    @field_validator("choices")
    @classmethod
    def validate_translate_choices(cls, v):
        if not isinstance(v, dict):
            raise ValueError("choices must be a dictionary")

        if len(v) < 1:
            raise ValueError("must have any choices")

        for choice_key, choice_label in v.items():
            if isinstance(choice_label, dict):
                v[choice_key] = translate_text(choice_label)

        return v

    def get_field_class_args(self) -> dict:
        args = super().get_field_class_args()
        args["choices"] = list(self.choices.items())
        return args


class SelectField(ChoiceField):
    kind: Literal["select"]
    _field_class: type[Field] = fields.ChoiceField
    _widget: type[Widget] = widgets.Select


class MultiSelectField(ChoiceField):
    kind: Literal["multiselect"]
    _field_class: type[Field] = fields.MultipleChoiceField
    _widget: type[Widget] = widgets.SelectMultiple


class RadioField(ChoiceField):
    kind: Literal["radio"]
    _field_class: type[Field] = fields.ChoiceField
    _widget: type[Widget] = widgets.RadioSelect


class CheckboxField(ChoiceField):
    kind: Literal["multicheckbox"]
    _field_class: type[Field] = fields.MultipleChoiceField
    _widget: type[Widget] = widgets.CheckboxSelectMultiple


class FileField(DynaformField):
    kind: Literal["file"]
    _field_class: type[Field] = fields.FileField
    _widget: type[Widget] = widgets.ClearableFileInput

    upload_prefix: str
    encrypt: bool = False
    pubkeys: list[str] = []

    @field_validator("upload_prefix")
    @classmethod
    def upload_prefix_must_be_simple(cls, v):
        if not re.fullmatch(SIMPLE_IDENTIFIER_PATTERN, v):
            raise ValueError("may contain ASCII letters, numbers, dashes and underscores only")
        return v

    @field_validator("pubkeys")
    @classmethod
    def pubkeys_must_be_simple(cls, v):
        for key in v:
            if not re.fullmatch(SIMPLE_IDENTIFIER_PATTERN, key):
                raise ValueError("pubkey name must contain ASCII letters, numbers, dashes and underscores only")
        return v

    def get_field_class_args(self) -> dict:
        args = super().get_field_class_args()
        for key in ("upload_prefix", "encrypt", "pubkeys"):
            if key in args:
                del args[key]

        return args


DynaformFieldUnion = Annotated[
    Union[  # noqa: UP007
        DynaformTemplate,
        CharField,
        TextField,
        URLField,
        EmailField,
        PhoneNumberField,
        BooleanField,
        CounterField,
        SelectField,
        MultiSelectField,
        RadioField,
        CheckboxField,
        FileField,
    ],
    PydanticField(discriminator="kind"),
]


class Dynaform(BaseModel):
    _prefix: str | None = None
    fields: dict[str, DynaformFieldUnion]

    @classmethod
    def build(cls, name: str | None, template: str) -> "Dynaform":
        df = cls.model_validate_json(template)
        df.set_prefix(name)
        return df

    @classmethod
    def collect_form_element_names(cls, v: dict[str, DynaformFieldUnion]) -> list[str]:
        names: list[str] = []

        if not v or not isinstance(v, dict):
            return names

        for name, field in v.items():
            if field.is_form_field():
                names.append(name)

        return names

    @field_validator("fields")
    @classmethod
    def check_unique_fields(cls, v: dict[str, DynaformFieldUnion]):
        names = Dynaform.collect_form_element_names(v)
        seen_names: set[str] = set()
        duplicated_names: set[str] = set()

        for name in names:
            if name in seen_names:
                duplicated_names.add(name)

            seen_names.add(name)

        if duplicated_names:
            raise pydantic.ValidationError(f"Dynamic form has duplicated field names: {duplicated_names}")

        return v

    @field_validator("fields")
    @classmethod
    def check_encrypted_pubkeys(cls, v: dict[str, DynaformFieldUnion]):
        for _name, field in v.items():
            if not isinstance(field, FileField):
                continue

            if not field.encrypt:
                continue

            if not field.pubkeys:
                raise pydantic.ValidationError("Pubkeys must be provided if encryption is enabled.")

        return v

    def get_prefix(self):
        return self._prefix or ""

    def set_prefix(self, name: str | None):
        if name:
            self._prefix = f"df__{name}__"
        else:
            self._prefix = ""

    def get_fields(self):
        computed_fields = {}
        prefix = self.get_prefix()

        field_config: DynaformNode
        for field_name, field_config in self.fields.items():
            if isinstance(field_config, DynaformField):
                name = prefix + field_name
                computed_fields[name] = field_config.get_field(name)

        return computed_fields

    def get_layout_objects(self):
        layout_objects = []
        prefix = self.get_prefix()

        field_config: DynaformNode
        for field_name, field_config in self.fields.items():
            if layout_object := field_config.get_layout_object(prefix + field_name):
                layout_objects.append(layout_object)

        return layout_objects


def dynaform_prefix(name: str | None) -> str:
    if name:
        return f"df__{name}__"
    else:
        return ""


def dynaform_to_fields(name: str | None, template: str) -> dict[str, Field]:
    dynaform = Dynaform.build(name, template)
    return dynaform.get_fields()
