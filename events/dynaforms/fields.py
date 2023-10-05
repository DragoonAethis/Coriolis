from abc import ABC
from typing import Literal, Optional, Union, Annotated

import pydantic
from django.forms import fields, widgets
from django.forms.fields import Field
from django.forms.widgets import Widget
from phonenumber_field import formfields as pnfields
from pydantic import field_validator, BaseModel, Field as PydanticField

from events.dynaforms.utils import parse_text_type_transform


class DynaformNode(BaseModel, ABC):
    kind: Literal[None]
    _field_class: type[Field] | None = None
    _widget: type[Widget] | None = None

    label: str
    label_type: Literal["text", "markdown", "html"] = "text"

    def is_form_field(self):
        """Determines if a node is a form field. True for things like
        text inputs or checkboxes, False for things like headers and images."""
        return self._field_class is not None


class DynaformField(DynaformNode, ABC):
    help_text: Optional[str] = None
    help_text_type: Literal["text", "markdown", "html"] = "text"

    required: bool = True

    def get_field_class_args(self) -> dict:
        args = self.model_dump()

        if "kind" in args:
            del args["kind"]

        if self._widget is not None:
            args["widget"] = self._widget

        parse_text_type_transform(args, "label", "label_type")
        parse_text_type_transform(args, "help_text", "help_text_type")

        return args

    def get_field(self) -> Field | None:
        if self._field_class is None:
            return None

        return self._field_class(**self.get_field_class_args())


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


class ChoiceField(DynaformField, ABC):
    choices: dict[str, str]

    @field_validator("choices")
    @classmethod
    def must_have_any_choices(cls, v):
        if len(v) == 0:
            raise ValueError("must have any choices")
        return v

    def get_field_class_args(self) -> dict:
        args = super().get_field_class_args()
        args["choices"] = [(k, v) for k, v in self.choices.items()]
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


DynaformFieldUnion = Annotated[
    Union[
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
    ],
    PydanticField(discriminator="kind"),
]


class Dynaform(BaseModel):
    _prefix: Optional[str] = None
    fields: dict[str, DynaformFieldUnion]

    @classmethod
    def build(cls, name: Optional[str], template: str) -> "Dynaform":
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

    def get_prefix(self):
        return self._prefix or ""

    def set_prefix(self, name: Optional[str]):
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
                computed_fields[prefix + field_name] = field_config.get_field()

        return computed_fields


def dynaform_prefix(name: Optional[str]) -> str:
    if name:
        return f"df__{name}__"
    else:
        return ""


def dynaform_to_fields(name: Optional[str], template: str) -> dict[str, Field]:
    dynaform = Dynaform.build(name, template)
    return dynaform.get_fields()
