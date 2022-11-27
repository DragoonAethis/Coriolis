from django import forms
from django.urls import reverse
from django.forms.widgets import TextInput, Textarea
from django.utils.translation import gettext_lazy as _

from phonenumber_field.formfields import PhoneNumberField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from events.models import Event, ApplicationType
from events.dynaforms.fields import dynaform_to_fields


class ApplicationDynaform(forms.Form):

    name = forms.CharField(label=_("First and last name/organization name"), max_length=256, required=True,
                           help_text=_("Your first and last name as shown on the identifying document, "
                                       "or the organization you represent."))
    email = forms.EmailField(label=_("E-mail Address"), required=True, widget=TextInput(),
                             help_text=_("E-mail address for notifications."))
    phone = PhoneNumberField(label=_("Phone Number"), required=True,
                             help_text=_("Required for notifications and contact with organizers."))

    DYNAFORM_NAME = 'act'

    def __init__(self, *args, event: Event, application_type: ApplicationType, template: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dynamic_fields = dynaform_to_fields(self.DYNAFORM_NAME, template)

        self.fields.update(self.dynamic_fields)
        self.fields['notes'] = forms.CharField(label=_("Notes"), required=False, widget=Textarea,
                                               help_text=_("Optional extra notes - add anything you want!"))

        self.helper = FormHelper()
        self.helper.form_action = 'post'
        self.helper.form_action = reverse('application_form', kwargs={
            "slug": event.slug,
            "id": application_type.id
        })
        self.helper.attrs['novalidate'] = True
        self.helper.add_input(Submit('submit', _('Submit Application'), css_class="btn btn-lg btn-primary"))
