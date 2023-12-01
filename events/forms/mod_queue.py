from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from events.models import Event, Ticket


class TicketModQueueDepersonalizeForm(forms.Form):
    clear_nickname = forms.BooleanField(label=_("Clear Nickname"), initial=False)
    clear_image = forms.BooleanField(label=_("Clear Image"), initial=True)

    def __init__(self, *args, event: Event, ticket: Ticket, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_action = "post"
        self.helper.form_action = reverse(
            "mod_queue_depersonalize", kwargs={"slug": event.slug, "ticket_id": ticket.id}
        )
        self.helper.add_input(Submit("submit", _("Depersonalize"), css_class="btn btn-lg btn-danger w-100"))
