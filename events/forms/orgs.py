import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class BillingDetailsForm(forms.Form):
    name = forms.CharField(
        label=_("Company name or your first and last name"),
        max_length=256,
    )
    tax_id = forms.CharField(
        label=_("Tax identifier"),
        max_length=256,
        help_text=_("PESEL for individuals, NIP for companies."),
    )

    address = forms.CharField(max_length=256, label=_("Address"))
    postcode = forms.CharField(max_length=256, label=_("Postcode"))
    city = forms.CharField(max_length=256, label=_("City"))

    def clean_tax_id(self):
        code = self.cleaned_data["tax_id"].strip()
        if not (code.isnumeric() and (10 <= len(code) <= 11)):
            raise ValidationError(_("This does not look like a valid tax identifier."))

        return code

    def clean_postcode(self):
        code = self.cleaned_data["postcode"].strip()
        if not re.match(r"\d{2}-?\d{3}", code):
            raise ValidationError(_("This does not look like a valid postcode."))

        return code
