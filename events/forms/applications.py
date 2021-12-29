from django import forms
from phonenumber_field.formfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
from django.forms.widgets import Textarea, TextInput
from django.urls import reverse

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class ApplicationForm(forms.Form):
    name = forms.CharField(label=_("First and last name/organization name"), max_length=256, required=True,
                           help_text=_("Your first and last name as shown on the identifying document, "
                                       "or the organization you represent."))
    email = forms.EmailField(label=_("E-mail Address"), required=True, widget=TextInput(),
                             help_text=_("E-mail address for notifications."))
    phone = PhoneNumberField(label=_("Phone Number"), required=True,
                             help_text=_("Required for notifications and contact with organizers."))
    age_gate = forms.BooleanField(label=_("I am at least 16 years old"), required=True,
                                  help_text=_("We cannot legally accept help or organization proposals "
                                              "from younger people."))

    def __init__(self, *args, event, type, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = 'post'
        self.helper.form_action = reverse('application_form', kwargs={
            "slug": event.slug,
            "id": type.id
        })
        self.helper.add_input(Submit('submit', _('Submit Application'), css_class="btn btn-lg btn-primary"))
