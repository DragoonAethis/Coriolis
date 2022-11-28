from abc import ABC
from typing import Literal, Optional, Union, ClassVar, Annotated

from django.forms.fields import Field
from django.forms.widgets import Widget
from django.forms import fields, widgets
from phonenumber_field import formfields as pnfields

from pydantic import validator, BaseModel, Field as PydanticField


class DynaformField(BaseModel, ABC):
    kind: Literal[None]
    _field_class: ClassVar[Field] = None
    _widget: ClassVar[Widget] = None

    label: str
    required: bool = True
    help_text: Optional[str] = None


class ChoiceField(DynaformField, ABC):
    choices: dict[str, str]

    @validator('choices')
    def must_have_any_choices(cls, v):
        if len(v) == 0:
            raise ValueError('must have any choices')
        return v


class CharField(DynaformField):
    kind: Literal['char']
    _field_class: ClassVar[Field] = fields.CharField


class TextField(DynaformField):
    kind: Literal['text']
    _field_class: ClassVar[Field] = fields.CharField
    _widget = widgets.Textarea


class EmailField(DynaformField):
    kind: Literal['email']
    _field_class: ClassVar[Field] = fields.EmailField


class PhoneNumberField(DynaformField):
    kind: Literal['phone']
    _field_class: ClassVar[Field] = pnfields.PhoneNumberField


class BooleanField(DynaformField):
    kind: Literal['checkbox']
    _field_class: ClassVar[Field] = fields.BooleanField


class SelectField(ChoiceField):
    kind: Literal['select']
    _field_class: ClassVar[Field] = fields.ChoiceField
    _widget: ClassVar[Widget] = widgets.Select


class MultiSelectField(ChoiceField):
    kind: Literal['multiselect']
    _field_class: ClassVar[Field] = fields.MultipleChoiceField
    _widget: ClassVar[Widget] = widgets.SelectMultiple


class RadioField(ChoiceField):
    kind: Literal['radio']
    _field_class: ClassVar[Field] = fields.ChoiceField
    _widget: ClassVar[Widget] = widgets.RadioSelect


class CheckboxField(ChoiceField):
    kind: Literal['multicheckbox']
    _field_class: ClassVar[Field] = fields.MultipleChoiceField
    _widget: ClassVar[Widget] = widgets.CheckboxSelectMultiple


DynaformFieldUnion = Annotated[Union[
    CharField,
    TextField,
    EmailField,
    PhoneNumberField,
    BooleanField,
    SelectField,
    MultiSelectField,
    RadioField,
    CheckboxField,
], PydanticField(discriminator='kind')]


class DynaformFieldConfiguration(BaseModel):
    fields: dict[str, DynaformFieldUnion]


def transform_choices(choices) -> list[(str, str)]:
    return [(k, v) for k, v in choices.items()]


def dynaform_prefix(name: Optional[str]) -> str:
    if name:
        return f"df__{name}__"
    else:
        return ""


def dynaform_to_fields(name: Optional[str], template: str) -> dict[str, Field]:
    config = DynaformFieldConfiguration.parse_raw(template)
    prefix = dynaform_prefix(name)
    dynamic_fields = {}

    field_config: DynaformField
    for field_name, field_config in config.fields.items():
        config_args = field_config.dict()

        if 'kind' in config_args:
            del config_args['kind']

        if field_config._widget is not None:
            config_args['widget'] = field_config._widget

        if 'choices' in config_args:
            config_args['choices'] = transform_choices(config_args['choices'])

        dynamic_fields[prefix + field_name] = field_config._field_class(**config_args)

    return dynamic_fields
