from decimal import Decimal

from django import forms
from payments.models import BasePayment

from .config import Przelewy24Config


class ProcessForm(forms.Form):
    merchantId = forms.IntegerField()
    posId = forms.IntegerField()
    sessionId = forms.CharField()
    amount = forms.IntegerField()
    originAmount = forms.IntegerField()
    currency = forms.CharField()
    orderId = forms.IntegerField()
    methodId = forms.IntegerField()
    statement = forms.CharField()
    sign = forms.CharField()

    def __init__(self, payment: BasePayment, config: Przelewy24Config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.payment = payment

    def clean(self):
        cleaned_data = super().clean()
        sign = cleaned_data.get("sign", "-1")
        sessionId = cleaned_data.get("sessionId", "-1")
        generated_sign = self.config.generate_sign(
            merchantId=cleaned_data.get("merchantId", 0),
            posId=cleaned_data.get("posId", 0),
            sessionId=cleaned_data.get("sessionId", ""),
            amount=cleaned_data.get("amount", 0),
            originAmount=cleaned_data.get("originAmount", 0),
            currency=cleaned_data.get("currency", ""),
            orderId=cleaned_data.get("orderId", 0),
            methodId=cleaned_data.get("methodId", 0),
            statement=cleaned_data.get("statement", ""),
        )

        if sign != generated_sign:
            raise forms.ValidationError(
                f"Incorrect hash: p24_sign={sign} sign={generated_sign}"
            )

        if sessionId != str(self.payment.pk):
            raise forms.ValidationError(
                f"Incorect payment ID: sessionId: {sessionId}, paymentId: {self.payment.pk}"
            )

        return cleaned_data

    def save(self, *args, **kwargs):
        self.payment.transaction_id = self.cleaned_data["statement"]
        self.payment.captured_amount = (
            self.payment.captured_amount + Decimal(self.cleaned_data["amount"]) / 100
        )
        self.payment.save()
