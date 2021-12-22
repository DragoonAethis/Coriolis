from django import forms
from django.forms import Textarea
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, HTML
from crispy_forms.bootstrap import FormActions

class RegistrationForm(forms.Form):
    name = forms.CharField(label=_("Name"), max_length=256, required=True,
                           help_text=_("Your first and last name, as shown on the identifying document."))
    email = forms.EmailField(label=_("E-mail Address"), required=True,
                             help_text=_("E-mail address for notifications."))
    phone = PhoneNumberField(label=_("Phone Number"), required=False,
                             help_text=_("Optional, used for SMS notifications. "
                                         "Organizers can contact you this way as well."))

    notes = forms.CharField(label=_("Notes for Organizers"), required=False, widget=Textarea,
                            help_text=_("Optional, add some notes for organizers who will have to "
                                        "read them before the ticket is ready for use on the event."))

    nickname = forms.CharField(label=_("Nickname"), max_length=256, required=False,
                               help_text=_("Optional, your nickname to be printed on your ticket."))
    city = forms.CharField(label=_("City"), max_length=256, required=False,
                           help_text=_("Optional, city to be printed on your ticket."))
    image = forms.ImageField(label=_("Image"), required=False,
                             help_text=_("Optional, image to be printed on your ticket."))

    def __init__(self, *args, event, type, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = 'post'
        self.helper.form_action = reverse('registration_form', kwargs={
            "slug": event.slug,
            "id": type.id
        })
        self.helper.layout = Layout(
            Fieldset(
                _("Details"),
                'name',
                'email',
                'phone',
                'notes',

                HTML("<h2>" + _("Personalization") + "</h2>"),
                HTML('<div><p>' + _("We can print your ticket with your own nickname and image on it. "
                                    "If you don't want a custom ticket, leave these fields empty.") + '</p></div>'),
                HTML('<div class="alert alert-warning">' + _('Only tickets paid online will be printed.') + '</div>'),
                'nickname',
                'city',
                'image'
            ),
            FormActions(
                Submit('submit', _('Register'), css_class="btn btn-lg btn-primary")
            )
        )


class CancelRegistrationForm(forms.Form):
    confirm = forms.BooleanField(label=_("I am sure - cancel this ticket!"), required=True)

    def __init__(self, *args, event, ticket, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = 'post'
        self.helper.form_action = reverse('ticket_cancel', kwargs={
            "slug": event.slug,
            "ticket_id": ticket.id
        })
        self.helper.add_input(Submit('submit', _('Cancel ticket'), css_class="btn btn-lg btn-danger"))
