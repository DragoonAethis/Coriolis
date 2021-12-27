import hashlib
import json
import logging
from dataclasses import asdict, dataclass

import requests

from .config import Przelewy24Config

logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    amount: int
    sessionId: str
    currency: str
    description: str
    email: str
    country: str
    language: str


@dataclass
class TransactionDTO:
    merchantId: int
    posId: int
    sessionId: str
    amount: int
    currency: str
    description: str
    email: str
    country: str
    language: str
    urlReturn: str
    urlStatus: str
    sign: str
    # cart: List[ItemDTO]

    @classmethod
    def create_from(
        cls,
        transaction: Transaction,
        config: Przelewy24Config,
        sign: str,
        success_url: str,
        status_url: str,
    ):
        return cls(
            merchantId=config.merchant_id,
            posId=config.merchant_id,
            sessionId=transaction.sessionId,
            amount=transaction.amount,
            currency=transaction.currency,
            description=transaction.description,
            email=transaction.email,
            country=transaction.country,
            language=transaction.language,
            urlReturn=success_url,
            urlStatus=status_url,
            sign=sign,
        )


@dataclass
class VerifyDTO:
    merchantId: int
    posId: int
    sessionId: str
    amount: int
    currency: str
    orderId: int
    sign: str

    @classmethod
    def create_from(
        cls,
        *,
        orderId: int,
        transaction: Transaction,
        config: Przelewy24Config,
        sign: str,
    ):
        return cls(
            merchantId=config.merchant_id,
            posId=config.merchant_id,
            sessionId=transaction.sessionId,
            amount=transaction.amount,
            currency=transaction.currency,
            orderId=orderId,  # TODO
            sign=sign,
        )


class Przelewy24API:
    def __init__(self, config: Przelewy24Config, session=None):
        self._http = session or requests.session()
        self._config = config
        super().__init__()

    def _do(self, method: str, endpoint: str, data=None):
        response = self._http.request(
            method=method,
            url=endpoint,
            json=data,
            auth=(str(self._config.pos_id), str(self._config.api_key)),
        )
        logger.debug(
            "%s %s: status_code=%s content=%s",
            method,
            endpoint,
            response.status_code,
            response.content.decode("utf-8"),
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Przelewy24 returns {response.status_code} instead of 200: {response.content}"
            )
        return response.json()

    def _create_sha386_sign(self, **kwargs) -> str:
        return hashlib.sha384(
            json.dumps(kwargs).replace(" ", "").encode("utf-8")
        ).hexdigest()

    def testConnection(self) -> bool:
        response = self._do("GET", self._config.endpoints.testConnection)
        return response["data"]

    def register(
        self, *, transaction: Transaction, success_url: str, status_url: str
    ) -> str:
        sign = self._config.generate_sign(
            sessionId=transaction.sessionId,
            merchantId=self._config.merchant_id,
            amount=transaction.amount,
            currency=transaction.currency,
        )

        transaction = TransactionDTO.create_from(
            transaction, self._config, sign, success_url, status_url
        )
        payload = asdict(transaction)
        response = self._do("POST", self._config.endpoints.transactionRegister, payload)
        token = response["data"]["token"]
        return f"{self._config.endpoints.transactionRequest}/{token}"

    def verify(self, *, transaction: Transaction, orderId: int) -> bool:
        sign = self._config.generate_sign(
            sessionId=transaction.sessionId,
            orderId=orderId,
            amount=transaction.amount,
            currency=transaction.currency,
        )
        verify = VerifyDTO.create_from(
            orderId=orderId, transaction=transaction, config=self._config, sign=sign
        )
        payload = asdict(verify)
        response = self._do("PUT", self._config.endpoints.transactionVerify, payload)
        return response["data"]["status"] == "success"

    def get_by_session_id(self, *, session_id: str) -> dict:
        return self._do("GET", self._config.endpoints.transactionGetBySessionId + session_id)
