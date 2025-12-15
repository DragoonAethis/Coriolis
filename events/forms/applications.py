from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Submit, Button
from django import forms
from django.forms.widgets import TextInput, Textarea
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from events.dynaforms.fields import Dynaform
from events.models import Event, Application, ApplicationType


class ApplicationDynaform(forms.Form):
    name = forms.CharField(
        label=_("First and last name/organization name"),
        max_length=256,
        required=True,
        help_text=_(
            "Your first and last name as shown on the identifying document, or the organization you represent."
        ),
    )
    email = forms.EmailField(
        label=_("Email Address"),
        required=True,
        widget=TextInput(),
        help_text=_("Email address for notifications and contact with organizers."),
    )
    phone = PhoneNumberField(
        label=_("Phone Number"),
        required=True,
        help_text=_(
            "Required for notifications and contact with organizers. (Add a country prefix, like +44 for the UK.)"
        ),
    )
    key = forms.CharField(
        label=_("Secret Key"),
        max_length=256,
        required=False,
        widget=forms.widgets.HiddenInput,
    )

    DYNAFORM_NAME = "act"

    def __init__(self, *args, event: Event, application_type: ApplicationType, template: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dynaform = Dynaform.build(ApplicationDynaform.DYNAFORM_NAME, template)
        self.dynamic_fields = self.dynaform.get_fields()

        self.fields.update(self.dynamic_fields)
        self.fields["notes"] = forms.CharField(
            label=_("Notes"),
            required=False,
            widget=Textarea,
            help_text=_("Optional extra notes - add anything you want!"),
        )

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field("name"),
            Field("email"),
            Field("phone"),
            *self.dynaform.get_layout_objects(),
            Field("notes"),
            Field("key"),
        )

        form_url = reverse("application_form", kwargs={"slug": event.slug, "id": application_type.id})
        if key := self.initial.get("key"):
            form_url += "?key=" + key

        self.helper.form_action = form_url
        self.helper.attrs["novalidate"] = True
        self.helper.add_input(Submit("submit", _("Submit Application"), css_class="btn btn-lg btn-primary"))


class ApplicationStatusSelfServiceForm(forms.Form):
    def __init__(self, event: Event, application: Application, flow: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_action = reverse(f"application_self_service_{flow}", kwargs={"slug": event.slug, "app_id": application.id})

        if flow == "approve":
            self.helper.add_input(Submit("submit", _("Approve"), css_class="btn btn-lg btn-success"))
        elif flow == "reject":
            self.helper.add_input(Submit("reject", _("Reject"), css_class="btn btn-lg btn-danger"))

        self.helper.add_input(Button(
            "cancel",
            _("Cancel"),
            css_class="btn btn-lg btn-secondary",
            onclick="window.history.back()"
        ))
