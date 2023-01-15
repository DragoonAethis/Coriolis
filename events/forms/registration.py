from django import forms
from django.forms import Textarea, TextInput
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, HTML
from crispy_forms.bootstrap import FormActions


class RegistrationForm(forms.Form):
    name = forms.CharField(label=_("First and last name"), max_length=256, required=True,
                           help_text=_("Your first and last name, as shown on the identifying document."))
    email = forms.EmailField(label=_("E-mail Address"), required=True, widget=TextInput(),
                             help_text=_("E-mail address for notifications."))
    phone = PhoneNumberField(label=_("Phone Number"), required=False,
                             help_text=_("Optional, used for SMS notifications. "
                                         "Organizers can contact you this way as well. "
                                         "(Add a country prefix, like +44 for the UK.)"))

    age_gate = forms.BooleanField(label=_("I am at least 18 years old"), required=False,
                                  help_text=_("If not, you must take extra documents listed above to the event."))
    regulations = forms.BooleanField(label=_("I accept the event regulations"), required=True,
                                     help_text=_("Regulations are listed above."))

    notes = forms.CharField(label=_("Notes for Organizers"), required=False, widget=Textarea,
                            help_text=_("Optional, add some notes for organizers who will have to "
                                        "read them before the ticket is ready for use on the event. "
                                        "Online payments will be available after approval."))

    def __init__(self, *args, event, ticket_type, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = 'post'
        self.helper.form_action = reverse('registration_form', kwargs={
            "slug": event.slug,
            "id": ticket_type.id
        })
        self.helper.attrs['novalidate'] = True
        self.helper.layout = Layout(
            Fieldset(
                _("Details"),
                'name',
                'email',
                'phone',
                'age_gate',
                'regulations',
                'notes',
            ),
            FormActions(
                Submit('submit', _('Register'), css_class="btn btn-lg btn-primary")
            )
        )


class UpdateTicketForm(forms.Form):
    nickname = forms.CharField(label=_("Nickname"), max_length=64, required=False,
                               help_text=_("Optional, your nickname to be printed on your ticket."))
    shirt_size = forms.TypedChoiceField(
        label=_("Shirt Size"), required=True,
        help_text=_("Sizes: wearer's height/chest."),
        choices=[
            ('S',   'S (168/93cm)'),
            ('M',   'M (176/99cm)'),
            ('L',   'L (182/106cm)'),
            ('XL',  'XL (185/113cm)'),
            ('2XL', '2XL (188/120cm)'),
            ('3XL', '3XL (188/128cm)'),
            ('4XL', '4XL (190/137cm)'),
            ('5XL', '5XL (big boi)'),
        ]
    )
    image = forms.ImageField(label=_("Image"), required=False,
                             help_text=_("Optional, image to be printed on your ticket."))
    keep_current_image = forms.BooleanField(label=_("Keep Current Image"), required=False,
                                            help_text=_("If checked, the image currently uploaded "
                                                        "on your ticket will not be changed."))

    def __init__(self, *args, event, ticket, **kwargs):
        super().__init__(*args, **kwargs)

        if not ticket.type.can_specify_shirt_size:
            del self.fields['shirt_size']

        self.helper = FormHelper()
        self.helper.form_action = 'post'
        self.helper.form_action = reverse('ticket_update', kwargs={
            "slug": event.slug,
            "ticket_id": ticket.id
        })
        self.helper.add_input(Submit('submit', _('Change ticket'), css_class="btn btn-lg btn-primary"))


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
