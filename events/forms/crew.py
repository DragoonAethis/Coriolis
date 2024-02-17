from crispy_forms.bootstrap import FieldWithButtons
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout
from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from events.models import Event, Ticket, TicketType


class CrewFindTicketForm(forms.Form):
    query = forms.CharField(
        label=_("Code, name, email, phone or nickname"),
        max_length=256,
        required=True,
        help_text=_("Numeric codes only, without the prefix."),
    )

    def __init__(self, *args, event: Event, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.layout = Layout(
            FieldWithButtons(
                "query",
                Submit("submit", _("Search"), css_class="btn btn-lg btn-primary"),
            )
        )

        self.helper.form_action = "post"
        self.helper.form_action = reverse("crew_find_ticket", kwargs={"slug": event.slug})


class CrewNewTicketForm(forms.Form):
    ticket_type = forms.ChoiceField(label=_("Ticket type"), widget=forms.RadioSelect)
    age_gate = forms.BooleanField(label=_("Is attendee of age?"), required=False)

    def __init__(self, *args, event: Event, types: list[TicketType], **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ticket_type"].choices = [
            (str(t.id), f"{t.name} ({t.price}, {t.tickets_remaining}/{t.max_tickets})") for t in types
        ]

        self.helper = FormHelper()
        self.helper.form_action = "post"
        self.helper.form_action = reverse("crew_index", kwargs={"slug": event.slug})
        self.helper.add_input(Submit("submit", _("Create"), css_class="btn btn-lg btn-primary w-100"))


class CrewUseTicketForm(forms.Form):
    def __init__(self, *args, event: Event, ticket: Ticket, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_action = "post"
        self.helper.form_action = reverse("crew_existing_ticket", kwargs={"slug": event.slug, "ticket_id": ticket.id})
        self.helper.add_input(Submit("submit", _("Use"), css_class="btn btn-lg btn-primary w-100"))
