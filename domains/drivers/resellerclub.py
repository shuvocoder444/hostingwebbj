"""
ResellerClub Domain Registrar Driver
=====================================
Interacts with ResellerClub's HTTP REST API.
Documentation: https://manage.resellerclub.com/kb/answer/751

Sandbox endpoint: https://test.httpapi.com/api/
Live endpoint:    https://httpapi.com/api/
"""
import logging
from typing import List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.exceptions import RegistrarDriverError, DomainRegistrationError, DomainRenewalError
from .base import BaseRegistrarDriver, DomainCheckResult, DomainRegistrationResult

logger = logging.getLogger('domains')


class ResellerClubDriver(BaseRegistrarDriver):
    """
    ResellerClub API implementation.
    """

    def __init__(self, api_user: str, api_key: str, is_sandbox: bool = True, extra_config: dict = None):
        super().__init__(api_user, api_key, is_sandbox, extra_config)
        self.reseller_id = str(api_user).strip()
        self.base_url = (
            "https://test.httpapi.com/api"
            if is_sandbox
            else "https://httpapi.com/api"
        )
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        return session

    def _call(self, endpoint: str, method: str = 'GET', params: dict = None, data: dict = None) -> dict:
        """Helper to invoke ResellerClub API with credentials."""
        url = f"{self.base_url}/{endpoint}.json"
        query_params = {
            'auth-userid': self.reseller_id,
            'api-key': self.api_key,
        }
        if params:
            query_params.update(params)

        try:
            if method.upper() == 'GET':
                resp = self._session.get(url, params=query_params, timeout=20)
            else:
                resp = self._session.post(url, params=query_params, data=data, timeout=25)
            
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            logger.error("ResellerClub API error on %s: %s", endpoint, exc)
            raise RegistrarDriverError(f"ResellerClub API error: {exc}")
        except ValueError as exc:
            raise RegistrarDriverError(f"ResellerClub returned invalid JSON: {exc}")

    def check_availability(self, domain: str) -> DomainCheckResult:
        """Check domain availability."""
        parts = domain.lower().strip().split('.')
        domain_name = parts[0]
        tld = ".".join(parts[1:])

        try:
            res = self._call('domains/available', method='GET', params={
                'domain-name': domain_name,
                'tlds': tld,
            })
            # ResellerClub returns: { "example.com": { "status": "available" | "regthroughothers" } }
            domain_info = res.get(domain, {})
            status = domain_info.get('status', 'unknown')
            is_avail = (status.lower() == 'available')

            return DomainCheckResult(
                domain=domain,
                is_available=is_avail,
                status="available" if is_avail else "taken",
                message="Domain is available!" if is_avail else f"Status: {status}",
            )
        except Exception as exc:
            logger.warning("ResellerClub check failed for %s: %s", domain, exc)
            return DomainCheckResult(domain=domain, is_available=False, status="error", message=str(exc))

    def register_domain(
        self,
        domain: str,
        years: int = 1,
        contact_info: dict = None,
        nameservers: Optional[List[str]] = None
    ) -> DomainRegistrationResult:
        """Register domain via ResellerClub."""
        contact_info = contact_info or {}
        ns_list = nameservers or ['ns1.hostpro.bd', 'ns2.hostpro.bd']

        payload = {
            'domain-name': domain,
            'years': str(years),
            'ns': ns_list,
            'customer-id': self.extra_config.get('customer_id', '1'),
            'reg-contact-id': self.extra_config.get('contact_id', '1'),
            'admin-contact-id': self.extra_config.get('contact_id', '1'),
            'tech-contact-id': self.extra_config.get('contact_id', '1'),
            'billing-contact-id': self.extra_config.get('contact_id', '1'),
            'invoice-option': 'NoInvoice',
            'protect-privacy': 'true',
        }

        try:
            res = self._call('domains/register', method='POST', data=payload)
            if res.get('status') == 'Success' or 'entityid' in res:
                order_id = str(res.get('entityid', ''))
                logger.info("Successfully registered domain %s on ResellerClub (Order #%s)", domain, order_id)
                return DomainRegistrationResult(
                    success=True,
                    domain=domain,
                    order_id=order_id,
                    message="Domain registered successfully!",
                    raw_response=res
                )
            else:
                error_msg = res.get('message', 'Unknown ResellerClub error')
                raise DomainRegistrationError(f"Registration failed: {error_msg}", detail=res)
        except Exception as exc:
            logger.error("ResellerClub domain registration exception: %s", exc)
            raise DomainRegistrationError(f"Could not register domain {domain}: {exc}")

    def renew_domain(self, domain: str, years: int = 1) -> DomainRegistrationResult:
        """Renew domain."""
        try:
            res = self._call('domains/renew', method='POST', data={
                'domain-name': domain,
                'years': str(years),
                'exp-date': self.extra_config.get('current_expiry_timestamp', '0'),
                'invoice-option': 'NoInvoice',
            })
            return DomainRegistrationResult(success=True, domain=domain, raw_response=res)
        except Exception as exc:
            raise DomainRenewalError(f"Domain renewal failed for {domain}: {exc}")

    def update_nameservers(self, domain: str, nameservers: List[str]) -> bool:
        """Modify nameservers."""
        try:
            res = self._call('domains/modify-ns', method='POST', data={
                'domain-name': domain,
                'ns': nameservers,
            })
            return res.get('status') == 'Success'
        except Exception as exc:
            logger.error("Failed to update nameservers for %s: %s", domain, exc)
            return False

    def get_domain_info(self, domain: str) -> dict:
        """Get live domain info."""
        return self._call('domains/details-by-name', method='GET', params={'domain-name': domain, 'options': 'All'})

    def get_account_balance(self) -> dict:
        """Check reseller wallet balance."""
        try:
            res = self._call('billing/reseller-balance', method='GET')
            return {
                'balance': res.get('sellingcurrencybalance', '0.00'),
                'currency': res.get('sellingcurrencysymbol', 'USD'),
            }
        except Exception as exc:
            return {'balance': '0.00', 'currency': 'USD', 'error': str(exc)}
