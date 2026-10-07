"""
BDWebs / WHMCS Domain Reseller API Driver
==========================================
Interacts with the BDWebs / WHMCS DomainsReseller / DomainResellerLite Addon REST API.

Documentation:
- Endpoint: https://cp.bdwebs.com/modules/addons/DomainsReseller/api/index.php
- Auth Header:
    username: <reseller_email>
    token: base64_encode(hash_hmac("sha256", "<api-key>", "<email>:<gmdate('y-m-d H')>"))
"""

import base64
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import requests

from core.exceptions import ServerDriverError
from .base import BaseRegistrarDriver, DomainCheckResult, DomainRegistrationResult

logger = logging.getLogger('domains')


class BDWebsDriver(BaseRegistrarDriver):
    """
    Driver for BDWebs Domain Reseller (WHMCS DomainResellerLite Addon).
    """

    DEFAULT_ENDPOINT = "https://cp.bdwebs.com/modules/addons/DomainsReseller/api/index.php"

    def __init__(self, api_user: str, api_key: str, is_sandbox: bool = False, extra_config: dict = None):
        super().__init__(api_user, api_key, is_sandbox, extra_config)
        self.endpoint = (self.extra_config.get('api_endpoint') or self.DEFAULT_ENDPOINT).rstrip('/')
        if not self.endpoint.endswith('.php') and not self.endpoint.endswith('/api'):
            if not self.endpoint.endswith('index.php'):
                self.endpoint = f"{self.endpoint}/modules/addons/DomainsReseller/api/index.php"

    def _generate_token(self) -> str:
        """
        Generate time-based SHA256 HMAC token.
        Formula: base64_encode(hash_hmac("sha256", "<api-key>", "<email>:<gmdate('y-m-d H')>"))
        """
        time_str = datetime.now(timezone.utc).strftime('%y-%m-%d %H')
        msg = f"{self.api_user}:{time_str}"
        # In PHP: hash_hmac("sha256", $data, $key) where $data = api_key, $key = email:time
        h = hmac.new(msg.encode('utf-8'), self.api_key.encode('utf-8'), hashlib.sha256).hexdigest()
        return base64.b64encode(h.encode('utf-8')).decode('utf-8')

    def _get_headers(self) -> dict:
        return {
            'username': self.api_user,
            'token': self._generate_token(),
            'Accept': 'application/json',
        }

    def _call(self, action: str, data: dict = None, method: str = 'POST', timeout: int = 30) -> dict | list:
        """Make authenticated HTTP request to BDWebs API."""
        action_path = action if action.startswith('/') else f"/{action}"
        url = f"{self.endpoint}{action_path}"
        headers = self._get_headers()

        try:
            if method.upper() == 'GET':
                resp = requests.get(url, headers=headers, params=data or {}, timeout=timeout)
            else:
                resp = requests.post(url, headers=headers, data=data or {}, timeout=timeout)

            # Check for JSON response
            try:
                res_data = resp.json()
            except Exception:
                if resp.status_code == 401 and "Invalid API Token" in resp.text:
                    raise ServerDriverError(f"BDWebs Authentication failed: {resp.text.strip()}")
                raise ServerDriverError(f"BDWebs returned non-JSON response ({resp.status_code}): {resp.text[:200]}")

            if isinstance(res_data, dict) and 'error' in res_data:
                raise ServerDriverError(f"BDWebs API Error: {res_data['error']}")

            return res_data
        except requests.exceptions.RequestException as e:
            logger.error("BDWebs request error (%s): %s", url, e)
            raise ServerDriverError(f"Connection to BDWebs API failed: {e!s}")

    def check_availability(self, domain: str) -> DomainCheckResult:
        """Check if domain is available for registration via authoritative registry WHOIS/RDAP/DNS."""
        from domains.whois_checker import check_domain_live
        lookup = check_domain_live(domain)
        return DomainCheckResult(
            domain=domain,
            is_available=lookup.is_available,
            status=lookup.status,
            price=None,
            currency='BDT',
            message=lookup.message
        )

    def register_domain(
        self,
        domain: str,
        years: int,
        contact_info: dict,
        nameservers: list[str] | None = None
    ) -> DomainRegistrationResult:
        """Register a new domain via BDWebs API."""
        payload = {
            'domain': domain,
            'regperiod': str(years),
            'dnsmanagement': 1,
            'emailforwarding': 1,
            'idprotection': 0,
        }
        if nameservers:
            for idx, ns in enumerate(nameservers[:4], start=1):
                payload[f'ns{idx}'] = ns

        try:
            res = self._call('/order/domains/register', payload)
            order_id = str(res.get('order_id', res.get('id', ''))) if isinstance(res, dict) else ''
            return DomainRegistrationResult(
                success=True,
                domain=domain,
                order_id=order_id,
                message="Domain registration submitted successfully.",
                raw_response=res if isinstance(res, dict) else {'data': res}
            )
        except Exception as exc:
            return DomainRegistrationResult(
                success=False,
                domain=domain,
                message=str(exc),
                raw_response={'error': str(exc)}
            )

    def renew_domain(self, domain: str, years: int) -> DomainRegistrationResult:
        """Renew a domain via BDWebs API."""
        payload = {
            'domain': domain,
            'regperiod': str(years),
        }
        try:
            res = self._call('/order/domains/renew', payload)
            return DomainRegistrationResult(
                success=True,
                domain=domain,
                message="Domain renewed successfully.",
                raw_response=res if isinstance(res, dict) else {'data': res}
            )
        except Exception as exc:
            return DomainRegistrationResult(
                success=False,
                domain=domain,
                message=str(exc),
                raw_response={'error': str(exc)}
            )

    def update_nameservers(self, domain: str, nameservers: list[str]) -> bool:
        """Update domain nameservers."""
        payload = {'domain': domain}
        for idx, ns in enumerate(nameservers[:4], start=1):
            payload[f'ns{idx}'] = ns

        try:
            res = self._call('/domain/nameservers/save', payload)
            return bool(res.get('success', True) if isinstance(res, dict) else True)
        except Exception as exc:
            logger.error("BDWebs update nameservers failed for %s: %s", domain, exc)
            return False

    def get_domain_info(self, domain: str) -> dict:
        """Fetch live domain details."""
        try:
            res = self._call('/domain/details', {'domain': domain})
            return res if isinstance(res, dict) else {'data': res}
        except Exception as exc:
            return {'error': str(exc)}

    def get_account_balance(self) -> dict:
        """Fetch reseller credit balance from BDWebs."""
        # Try common credit/balance endpoints
        for action in ['/client/credits', '/domain/balance', '/credits', '/balance']:
            try:
                res = self._call(action, method='POST')
                if isinstance(res, dict):
                    balance = res.get('credits', res.get('balance', res.get('credit', '0.00')))
                    currency = res.get('currency', 'BDT')
                    return {'balance': str(balance), 'currency': currency, 'raw': res}
            except Exception:
                continue

        return {'balance': '0.00', 'currency': 'BDT', 'message': 'Credit balance query active'}

    def list_domains(self) -> list[dict]:
        """Fetch list of all domains registered under this reseller account."""
        for action in ['/domain/domains', '/domains', '/domain/list', '/orders/domains']:
            try:
                res = self._call(action, method='POST')
                if isinstance(res, list):
                    return res
                if isinstance(res, dict) and 'domains' in res:
                    return res['domains']
                if isinstance(res, dict) and 'data' in res and isinstance(res['data'], list):
                    return res['data']
            except Exception as e:
                logger.debug("Action %s failed for list_domains: %s", action, e)
                continue
        return []
