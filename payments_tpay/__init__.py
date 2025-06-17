import json
import logging
import hashlib
import warnings
from enum import StrEnum
from decimal import Decimal
from urllib.parse import urljoin
from typing import TYPE_CHECKING

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http.response import HttpResponseBadRequest, HttpResponse

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient

from joserfc import jws
from joserfc.jwk import RSAKey, KeySet

from payments import PaymentStatus, get_payment_model
from payments.core import BasicProvider

if TYPE_CHECKING:
    Payment = get_payment_model()

# Grabbed on 2025-06-01 from https://secure.tpay.com/x509/notifications-jws.pem
# There's the right way, and then there's this way that does not drive me insane:
TPAY_JWS_PUBKEY = RSAKey.import_key("""
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA+bRRxTL4htkeVfTYryXz
wG/kSbJP2oS+ByEdHT0C3WTuQZIdpOCD4LSPB7IiJiD8rN4BXjG2u3IV9S5AwTc/
y7gNdychRvkcmgblr6nZ1Yl0DaQCAdK/J7rAYO+6HNTOjDlHG0WphrgkqpOy0LWG
M06fmz/e7lbd/JeLT2yJX1qMltPY0t1+zK795dJ5osAXUcS44TfwLR8PEAegwQcU
8uCyb1Wq9unaoBTR4hSSwbSN2WO2PTpa/MpEFwgnO8Wy7Kp9WY8xZVBR+MUtgthQ
Nii5pXmnYj5I6xstQbd7FFZN7j7jchqstfFGkkFG6YGrv1ds9e5WWxM+U6ST4u8j
4QIDAQAB
-----END PUBLIC KEY-----
""")

TPAY_JWS_KEYSET = KeySet([TPAY_JWS_PUBKEY])
TPAY_ENVIRONMENTS = {
    "production": "https://api.tpay.com",
    "sandbox": "https://openapi.sandbox.tpay.com",
}


class TpayApiClient(OAuth2Session):
    """
    A wrapper around a requests.Session that automatically handles
    Tpay base API and session handling. An instance of this class is
    valid only as long as the token in use is - up to a few minutes,
    if a cached token is reused, but up to 2 hours otherwise.

    TODO: Handle automatic token refreshing for long-lived clients.
    """
    base_url: str

    class Endpoint(StrEnum):
        AUTH = "/oauth/auth"
        TOKEN_INFO = "/oauth/tokeninfo"
        TRANSACTIONS = "/transactions"

    def __init__(
            self,
            base_url: str,
            client_id: str,
            client_secret: str,
    ):
        self.base_url = base_url
        client = BackendApplicationClient(client_id=client_id)
        super().__init__(client=client)

        token_cache_key = f"tpay-api-client-key.{self.client_id}"
        if cached_key := cache.get(token_cache_key):
            # Reuse the same key:
            self.token = json.loads(cached_key)
        else:
            # Fetch a new one (method updates self.token internally):
            self.token = self.fetch_token(
                token_url=urljoin(self.base_url, TpayApiClient.Endpoint.AUTH),
                include_client_id=True,
                client_secret=client_secret,
            )

            # Reuse it for subsequent requests, refresh when we've got <10% of time left:
            if token_timeout := self.token.get("expires_in"):
                cache_timeout = round(token_timeout * 0.9)
                cache.set(token_cache_key, json.dumps(self.token), timeout=cache_timeout)

    def request(self, method, url, *args, **kwargs):
        url = self.create_url(url)
        return super().request(method, url, *args, **kwargs)

    def prepare_request(self, request):
        """Prepare the request after generating the complete URL."""
        request.url = self.create_url(request.url)
        return super().prepare_request(request)

    def create_url(self, url):
        """Create the URL based off this partial path."""
        return urljoin(self.base_url, url)


class TpayProvider(BasicProvider):
    """
    Tpay-based payment provider for django-payments. This is currently
    only supported for
    """
    api_url: str
    client_id: str
    client_secret: str
    verification_code: str
    test_mode: bool

    def __init__(
            self,
            client_id: str,
            client_secret: str,
            verification_code: str,
            environment: str = "production",
            api_url: str | None = None,
            test_mode: bool = False,
    ):
        super().__init__()
        self.api_url = api_url.strip() or TPAY_ENVIRONMENTS.get(environment.lower().strip())
        if not api_url:
            raise ImproperlyConfigured("Provided Tpay environment unknown - set the api_url instead")

        self.client_id = client_id
        self.client_secret = client_secret
        self.verification_code = verification_code
        self.test_mode = test_mode

        if (self.api_url == TPAY_ENVIRONMENTS["production"]) and test_mode:
            warnings.warn("Accepting test mode payments on the production Tpay API endpoint!", RuntimeWarning)

    def get_hidden_fields(self, payment):
        return {}

    def get_action(self, payment: "Payment"):
        merchant_description = f"Payment ID {payment.id} - Ticket ID {payment.ticket.id} - User {payment.user.email}"
        payload = {
            "amount": float(payment.total),
            "description": payment.description[:127],
            "hiddenDescription": merchant_description[:254],
            "payer": {
                "email": payment.billing_email,
                "name": payment.ticket.name[:254],
            },
            "callbacks": {
                "payerUrls": {
                    "success": payment.get_success_url(),
                    "error": payment.get_failure_url(),
                },
                "notification": {
                    "url": self.get_return_url(payment),
                },
            },
        }

        client = TpayApiClient(self.api_url, self.client_id, self.client_secret)
        r = client.post("/transactions", json=payload)
        r.raise_for_status()
        data = r.json()

        # Keep all of this around, just in case:
        payment.transaction_id = data["title"]
        payment.extra_data = json.dumps(data)
        payment.message = data["title"]
        payment.save()

        url = data["transactionPaymentUrl"]
        logging.debug(f"Transaction registered: {url=}")
        return url

    # get_form - super() only

    def process_data(self, payment, request):
        if request.method != "POST":
            return HttpResponseBadRequest("Not a POST request")

        required_keys = ["id", "tr_id", "tr_amount", "tr_paid", "tr_crc", "tr_status"]
        for key in required_keys:
            if key not in request.POST:
                return HttpResponseBadRequest("Request is missing required data")

        if expected_md5sum := request.POST.get("md5sum"):
            part_names = ["id", "tr_id", "tr_amount", "tr_crc"]
            parts = [request.POST.get(name) for name in part_names] + [self.verification_code]
            calculated_md5sum = hashlib.md5("".join(parts).encode()).hexdigest()
            if expected_md5sum.lower() != calculated_md5sum.lower():
                return HttpResponseBadRequest("Signature/checksum verification error")

        signature_header = request.headers.get("X-Jws-Signature")
        if not signature_header:
            return HttpResponseBadRequest("Signature/checksum verification error")

        # TODO: Perform the full JWS signature verification
        # While the md5sum/verification code flow above works "good enough",
        # it's really not

        # This field might be optional on prod?
        payment_in_test_mode = request.POST.get("test_mode").strip() == "1"
        if not self.test_mode and payment_in_test_mode:
            return HttpResponseBadRequest("Payment was done in test mode on a production system")

        if request.POST["tr_id"] != payment.transaction_id:
            return HttpResponseBadRequest("Expected a different transaction ID")

        if request.POST["tr_amount"] != request.POST["tr_paid"]:
            return HttpResponseBadRequest("Invalid amount paid (expected full, cannot handle other cases yet)")

        payment_status = request.POST["tr_status"].strip().lower()
        logging.debug(f"{payment.id=} being set per {payment_status=}")

        # Capture and save one last time:
        payment.captured_amount = Decimal(request.POST["tr_paid"])
        payment.save()

        if payment_status == "true":
            payment.change_status(PaymentStatus.CONFIRMED)
        elif payment_status == "chargeback":
            payment.change_status(PaymentStatus.REFUNDED)
        else:
            return HttpResponseBadRequest("Payment status not understood")

        # Tpay expects this exact body to ack the notification on their side:
        return HttpResponse("TRUE")
