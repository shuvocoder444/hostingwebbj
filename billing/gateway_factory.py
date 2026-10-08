"""
Payment Gateway Integrations
==============================
Implements bKash and SSLCommerz payment gateways.

Architecture:
  - BasePaymentGateway defines the interface.
  - Each gateway handles: initiation, IPN verification, status check.
  - IPN signature verification is MANDATORY before recording any payment.
  - get_payment_gateway() factory selects at runtime.

Security:
  - IPN endpoints verify gateway signature before trusting any data.
  - Gateway credentials loaded from settings (env-backed).
  - All raw IPN data is stored in Transaction.gateway_response for audit.
"""

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

import requests
from django.conf import settings

from core.exceptions import PaymentGatewayError, InvalidIPNSignature
from billing.models import Invoice

logger = logging.getLogger('billing')


# ─── Base Gateway ─────────────────────────────────────────────────────────────

class BasePaymentGateway(ABC):
    """Interface all payment gateways must implement."""

    @abstractmethod
    def initiate_payment(self, invoice: Invoice, customer, callback_url: str) -> dict:
        """
        Initiate a payment session.
        Returns dict with 'payment_url' key for client redirect.
        """
        ...

    @abstractmethod
    def verify_ipn(self, request_data: dict, request_headers: dict) -> bool:
        """
        Verify the IPN/webhook signature.
        Returns True if valid, raises InvalidIPNSignature otherwise.
        """
        ...

    @abstractmethod
    def get_payment_status(self, payment_id: str) -> dict:
        """Query gateway for current payment status."""
        ...


# ─── bKash Gateway ────────────────────────────────────────────────────────────

class BKashGateway(BasePaymentGateway):
    """
    bKash Tokenized Payment Gateway.
    Flow: grant token → create payment → redirect → execute → verify
    """

    BASE_URL: str = getattr(settings, 'BKASH_BASE_URL',
                            'https://tokenized.sandbox.bka.sh/v1.2.0-beta')

    def __init__(self):
        self.app_key = getattr(settings, 'BKASH_APP_KEY', '')
        self.app_secret = getattr(settings, 'BKASH_APP_SECRET', '')
        self.username = getattr(settings, 'BKASH_USERNAME', '')
        self.password = getattr(settings, 'BKASH_PASSWORD', '')

    def _get_access_token(self) -> str:
        """Obtain bKash access token, cached in Redis for 55 minutes."""
        from django.core.cache import cache
        cache_key = 'bkash:access_token'
        cached_token = cache.get(cache_key)
        if cached_token:
            return cached_token

        url = f"{self.BASE_URL}/tokenized/checkout/token/grant"
        headers = {
            'Content-Type': 'application/json',
            'username': self.username,
            'password': self.password,
        }
        payload = {'app_key': self.app_key, 'app_secret': self.app_secret}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"bKash token grant failed: {exc}")

        if 'id_token' not in data:
            raise PaymentGatewayError(
                f"bKash token grant error: {data.get('statusMessage', 'Unknown error')}"
            )

        token = data['id_token']
        cache.set(cache_key, token, timeout=3300)  # 55 min (tokens valid for 60 min)
        return token

    def _get_headers(self) -> dict:
        return {
            'Content-Type': 'application/json',
            'Authorization': self._get_access_token(),
            'X-APP-Key': self.app_key,
        }

    def initiate_payment(self, invoice: Invoice, customer, callback_url: str) -> dict:
        """Create a bKash payment and return the payment URL."""
        url = f"{self.BASE_URL}/tokenized/checkout/create"
        payload = {
            'mode': '0011',
            'payerReference': str(customer.id),
            'callbackURL': callback_url,
            'amount': str(invoice.total),
            'currency': 'BDT',
            'intent': 'sale',
            'merchantInvoiceNumber': invoice.invoice_number,
        }

        try:
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=20)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"bKash payment create failed: {exc}")

        if data.get('statusCode') != '0000':
            raise PaymentGatewayError(
                f"bKash create error: {data.get('statusMessage')}", detail=data
            )

        return {
            'payment_url': data['bkashURL'],
            'payment_id': data['paymentID'],
            'gateway': 'bkash',
        }

    def execute_payment(self, payment_id: str) -> dict:
        """Execute (capture) a bKash payment after customer approval."""
        url = f"{self.BASE_URL}/tokenized/checkout/execute"
        try:
            response = requests.post(
                url, json={'paymentID': payment_id},
                headers=self._get_headers(), timeout=20,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"bKash execute failed: {exc}")

    def verify_ipn(self, request_data: dict, request_headers: dict) -> bool:
        """Verify by calling bKash query API — we never trust redirect params alone."""
        payment_id = request_data.get('paymentID')
        if not payment_id:
            raise InvalidIPNSignature("bKash callback missing paymentID")

        status_data = self.get_payment_status(payment_id)
        if status_data.get('transactionStatus') != 'Completed':
            raise InvalidIPNSignature(
                f"bKash payment not completed: {status_data.get('transactionStatus')}",
                detail=status_data
            )
        return True

    def get_payment_status(self, payment_id: str) -> dict:
        """Query bKash payment status."""
        url = f"{self.BASE_URL}/tokenized/checkout/payment/status"
        try:
            response = requests.post(
                url, json={'paymentID': payment_id},
                headers=self._get_headers(), timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"bKash query failed: {exc}")


# ─── SSLCommerz Gateway ───────────────────────────────────────────────────────

class SSLCommerzGateway(BasePaymentGateway):
    """
    SSLCommerz Payment Gateway.
    IPN verified via SSLCommerz server-to-server validation API.
    """

    def __init__(self):
        self.store_id = getattr(settings, 'SSLCOMMERZ_STORE_ID', '')
        self.store_pass = getattr(settings, 'SSLCOMMERZ_STORE_PASS', '')
        is_sandbox = getattr(settings, 'SSLCOMMERZ_SANDBOX', True)
        self.base_url = (
            'https://sandbox.sslcommerz.com'
            if is_sandbox
            else 'https://securepay.sslcommerz.com'
        )

    def initiate_payment(self, invoice: Invoice, customer, callback_url: str) -> dict:
        """Initiate SSLCommerz session and return payment URL."""
        url = f"{self.base_url}/gwprocess/v4/api.php"
        payload = {
            'store_id': self.store_id,
            'store_passwd': self.store_pass,
            'total_amount': str(invoice.total),
            'currency': 'BDT',
            'tran_id': invoice.invoice_number,
            'success_url': callback_url,
            'fail_url': callback_url,
            'cancel_url': callback_url,
            'ipn_url': callback_url,
            'cus_name': customer.get_full_name(),
            'cus_email': customer.email,
            'cus_phone': getattr(getattr(customer, 'profile', None), 'phone', ''),
            'cus_add1': 'Dhaka',
            'cus_city': 'Dhaka',
            'cus_country': 'Bangladesh',
            'shipping_method': 'NO',
            'product_name': f'Invoice {invoice.invoice_number}',
            'product_category': 'Hosting',
            'product_profile': 'non-physical-goods',
        }

        try:
            response = requests.post(url, data=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"SSLCommerz session create failed: {exc}")

        if data.get('status') != 'SUCCESS':
            raise PaymentGatewayError(
                f"SSLCommerz init error: {data.get('failedreason')}", detail=data
            )

        return {
            'payment_url': data['GatewayPageURL'],
            'session_key': data['sessionkey'],
            'gateway': 'sslcommerz',
        }

    def verify_ipn(self, request_data: dict, request_headers: dict) -> bool:
        """
        Verify SSLCommerz IPN via server-to-server validation API.
        Never trust the IPN data alone — always call the validation endpoint.
        """
        val_id = request_data.get('val_id')
        if not val_id:
            raise InvalidIPNSignature("SSLCommerz IPN missing val_id")

        url = f"{self.base_url}/validator/api/validationserverAPI.php"
        params = {
            'val_id': val_id,
            'store_id': self.store_id,
            'store_passwd': self.store_pass,
            'format': 'json',
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"SSLCommerz validation failed: {exc}")

        if data.get('status') not in ('VALID', 'VALIDATED'):
            raise InvalidIPNSignature(
                f"SSLCommerz IPN validation failed: status={data.get('status')}",
                detail=data
            )
        return True

    def get_payment_status(self, payment_id: str) -> dict:
        url = f"{self.base_url}/validator/api/validationserverAPI.php"
        params = {
            'val_id': payment_id,
            'store_id': self.store_id,
            'store_passwd': self.store_pass,
            'format': 'json',
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            return response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"SSLCommerz status check failed: {exc}")


# ─── Cryptomus Gateway ────────────────────────────────────────────────────────

class CryptomusGateway(BasePaymentGateway):
    """
    Cryptomus Payment Gateway (Crypto USDT/BTC/ETH + Global Cards & Apple Pay).
    Official API: https://doc.cryptomus.com/business/payments/creating-invoice
    """
    BASE_URL: str = 'https://api.cryptomus.com/v1'

    def __init__(self):
        from core.models import SiteSetting
        setting = SiteSetting.get_settings()
        self.merchant_id = getattr(setting, 'cryptomus_merchant_id', '') or getattr(settings, 'CRYPTOMUS_MERCHANT_ID', '')
        self.payment_api_key = getattr(setting, 'cryptomus_payment_api_key', '') or getattr(settings, 'CRYPTOMUS_PAYMENT_API_KEY', '')

    def _generate_sign(self, data: dict) -> str:
        import base64
        import hashlib
        import json
        data_json = json.dumps(data, separators=(',', ':'))
        encoded = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
        return hashlib.md5((encoded + self.payment_api_key).encode('utf-8')).hexdigest()

    def initiate_payment(self, invoice: Invoice, customer, callback_url: str) -> dict:
        if not self.merchant_id or not self.payment_api_key:
            raise PaymentGatewayError("Cryptomus Merchant ID or Payment API Key is not configured in Admin Settings.")

        # Convert BDT to USD (125 BDT = 1 USD approx)
        amount_usd = round(float(invoice.total) / 125.0, 2)
        if amount_usd < 1.0:
            amount_usd = 1.0

        payload = {
            'amount': f"{amount_usd:.2f}",
            'currency': 'USD',
            'order_id': str(invoice.invoice_number),
            'url_return': f"https://velohoster.com/dashboard/?tab=invoices&paid_invoice={invoice.id}",
            'url_callback': callback_url,
            'is_payment_multiple': False,
            'lifetime': 3600,
        }

        sign = self._generate_sign(payload)
        headers = {
            'merchant': self.merchant_id,
            'sign': sign,
            'Content-Type': 'application/json',
        }

        url = f"{self.BASE_URL}/payment"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"Cryptomus payment session failed: {exc}")

        if data.get('state') != 0:
            raise PaymentGatewayError(f"Cryptomus error: {data.get('message', 'Unknown error')}", detail=data)

        result = data.get('result', {})
        return {
            'payment_url': result.get('url'),
            'payment_id': result.get('uuid'),
            'gateway': 'cryptomus',
        }

    def verify_ipn(self, request_data: dict, request_headers: dict) -> bool:
        if not self.payment_api_key:
            raise InvalidIPNSignature("Cryptomus API key missing on server.")

        import base64
        import hashlib
        import json

        data_copy = dict(request_data)
        sign = data_copy.pop('sign', None)
        if not sign:
            raise InvalidIPNSignature("Cryptomus webhook missing signature ('sign').")

        data_json = json.dumps(data_copy, separators=(',', ':'))
        encoded = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
        computed_sign = hashlib.md5((encoded + self.payment_api_key).encode('utf-8')).hexdigest()

        if sign != computed_sign:
            raise InvalidIPNSignature("Cryptomus signature verification failed.")

        status = data_copy.get('status', '').lower()
        if status not in ('paid', 'paid_over'):
            raise InvalidIPNSignature(f"Cryptomus payment status not paid: {status}")

        return True

    def get_payment_status(self, payment_id: str) -> dict:
        payload = {'uuid': payment_id}
        sign = self._generate_sign(payload)
        headers = {'merchant': self.merchant_id, 'sign': sign, 'Content-Type': 'application/json'}
        url = f"{self.BASE_URL}/payment/info"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            return response.json()
        except requests.RequestException as exc:
            raise PaymentGatewayError(f"Cryptomus status check failed: {exc}")


# ─── Gateway Factory ──────────────────────────────────────────────────────────

_GATEWAY_REGISTRY: dict[str, type[BasePaymentGateway]] = {
    'bkash': BKashGateway,
    'sslcommerz': SSLCommerzGateway,
    'cryptomus': CryptomusGateway,
}


def get_payment_gateway(name: str) -> BasePaymentGateway:
    """
    Return an initialised payment gateway instance.

    Args:
        name: Gateway identifier ('bkash', 'sslcommerz', 'cryptomus').

    Raises:
        PaymentGatewayError: If gateway name is not registered.
    """
    gateway_class = _GATEWAY_REGISTRY.get(name.lower())
    if gateway_class is None:
        raise PaymentGatewayError(
            f"Unknown payment gateway: '{name}'. "
            f"Available: {list(_GATEWAY_REGISTRY.keys())}"
        )
    return gateway_class()
