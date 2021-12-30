from typing import Optional

import phonenumber_field.formfields
from django import forms
from django.urls import reverse
from django.forms.widgets import TextInput, Textarea
from django.utils.translation import gettext_lazy as _

from phonenumber_field.formfields import PhoneNumberField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from events.models import Event, ApplicationType


class ApplicationDynaform(forms.Form):
    name = forms.CharField(label=_("First and last name/organization name"), max_length=256, required=True,
                           help_text=_("Your first and last name as shown on the identifying document, "
                                       "or the organization you represent."))
    email = forms.EmailField(label=_("E-mail Address"), required=True, widget=TextInput(),
                             help_text=_("E-mail address for notifications."))
    phone = PhoneNumberField(label=_("Phone Number"), required=True,
                             help_text=_("Required for notifications and contact with organizers."))

    def __init__(self, *args, event: Event, application_type: ApplicationType, template: str = None, **kwargs):
        super().__init__(*args, **kwargs)

        self.dynamic_fields = self.parse_template(template)
        self.dynamic_fields['notes'] = forms.CharField(label=_("Notes"), required=False, widget=Textarea,
                                                       help_text=_("Optional extra notes - add anything you want!"))

        self.fields.update(self.dynamic_fields)

        self.helper = FormHelper()
        self.helper.form_action = 'post'
        self.helper.form_action = reverse('application_form', kwargs={
            "slug": event.slug,
            "id": application_type.id
        })
        self.helper.attrs['novalidate'] = True
        self.helper.add_input(Submit('submit', _('Submit Application'), css_class="btn btn-lg btn-primary"))

    def parse_template(self, template: str) -> dict[str, forms.Field]:
        dynamic_fields = {}

        if template is None or len(template.strip()) == 0:
            return dynamic_fields

        for line in template.splitlines():
            line = line.strip()
            if len(line) == 0 or line.startswith('#'):
                continue

            key, field = self.parse_line_to_dynamic_field(line)
            if key is not None:
                dynamic_fields[key] = field

        return dynamic_fields

    @staticmethod
    def parse_line_to_dynamic_field(line: str) -> tuple[str, forms.Field]:
        parts = [x.strip() for x in line.split('|')]
        if len(parts) < 3:
            raise ValueError(f"Not enough parts to construct a field in line: {line}")

        field_key = parts[0]
        field_type = parts[1]
        kwargs = {'label': parts[2]}

        extras: dict[str, str] = {}
        extra_parts = [] if len(parts) == 3 else parts[3:]

        for extra_part in extra_parts:
            key, _, value = extra_part.partition(':')
            if len(key) == 0 or len(value) == 0:
                continue

            extras[key] = value

        kwargs['required'] = bool(int(extras.get('required', '1')))
        kwargs['help_text'] = extras.get('help', None)

        if 'choices' in extras:
            kwargs['choices'] = [(x.strip(), x.strip())
                                 for x in extras['choices'].split(';')]

        field_class: type[forms.Field]
        if field_type == 'text':
            field_class = forms.CharField
        elif field_type == 'email':
            field_class = forms.EmailField
        elif field_type == 'phone':
            field_class = PhoneNumberField
        elif field_type == 'checkbox':
            field_class = forms.BooleanField
        elif field_type == 'choices':
            if 'choices' not in kwargs:
                raise ValueError(f'Possible choices are required in line: {line}')

            field_class = forms.ChoiceField
        else:
            raise ValueError(f"Unknown field type {unknown} for line: {line}")

        return field_key, field_class(**kwargs)
