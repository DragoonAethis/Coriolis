from django import forms
from phonenumber_field.formfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
from django.forms.widgets import Textarea
from django.urls import reverse

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class ApplicationForm(forms.Form):
    name = forms.CharField(label=_("Name"), max_length=256, required=True,
                           help_text=_("Your first and last name, or the organization you represent."))
    email = forms.EmailField(label=_("E-mail Address"), required=True,
                             help_text=_("E-mail address for notifications."))
    phone = PhoneNumberField(label=_("Phone Number"), required=True,
                             help_text=_("Required for notifications and contact with organizers."))
    application = forms.CharField(label=_("Form"), required=True, widget=Textarea)

    def __init__(self, *args, event, type, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = 'post'
        self.helper.form_action = reverse('application_form', kwargs={
            "slug": event.slug,
            "id": type.id
        })
        self.helper.add_input(Submit('submit', _('Submit Application'), css_class="btn btn-lg btn-primary"))
