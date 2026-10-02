"""
Namecheap Domain Registrar Driver
==================================
Interacts with Namecheap's XML API.
Documentation: https://www.namecheap.com/support/api/methods/
"""
import logging
import xml.etree.ElementTree as ET
from typing import List, Optional
import requests

from core.exceptions import RegistrarDriverError, DomainRegistrationError, DomainRenewalError
from .base import BaseRegistrarDriver, DomainCheckResult, DomainRegistrationResult

logger = logging.getLogger('domains')


class NamecheapDriver(BaseRegistrarDriver):
    """
    Namecheap API implementation.
    """

    def __init__(self, api_user: str, api_key: str, is_sandbox: bool = True, extra_config: dict = None):
        super().__init__(api_user, api_key, is_sandbox, extra_config)
        self.endpoint = (
            "https://api.sandbox.namecheap.com/xml.response"
            if is_sandbox
            else "https://api.namecheap.com/xml.response"
        )
        self.client_ip = self.extra_config.get('client_ip', '127.0.0.1')
        self.username = self.extra_config.get('username', api_user)

    def _call(self, command: str, extra_params: dict = None) -> ET.Element:
        """Call Namecheap XML API and return parsed XML root."""
        params = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'UserName': self.username,
            'ClientIP': self.client_ip,
            'Command': command,
        }
        if extra_params:
            params.update(extra_params)

        try:
            resp = requests.get(self.endpoint, params=params, timeout=25)
            resp.raise_for_status()
            # Namecheap responses are XML
            root = ET.fromstring(resp.content)
            # Check for API error
            status = root.attrib.get('Status', '')
            if status.lower() == 'error':
                errors = root.find('{http://api.namecheap.com/xml.response}Errors')
                err_text = ""
                if errors is not None:
                    err_text = " ".join([e.text or '' for e in errors])
                raise RegistrarDriverError(f"Namecheap error: {err_text}")
            return root
        except ET.ParseError as exc:
            raise RegistrarDriverError(f"Failed to parse Namecheap XML: {exc}")
        except requests.RequestException as exc:
            raise RegistrarDriverError(f"Namecheap network error: {exc}")

    def check_availability(self, domain: str) -> DomainCheckResult:
        """Check domain availability via namecheap.domains.check."""
        try:
            root = self._call('namecheap.domains.check', {'DomainList': domain})
            # Find DomainCheckResult in namespace
            ns = {'nc': 'http://api.namecheap.com/xml.response'}
            elem = root.find('.//nc:DomainCheckResult', ns)
            if elem is not None:
                is_available = elem.attrib.get('Available', 'false').lower() == 'true'
                return DomainCheckResult(
                    domain=domain,
                    is_available=is_available,
                    status="available" if is_available else "taken",
                    message="Available" if is_available else "Registered",
                )
            return DomainCheckResult(domain=domain, is_available=False, status="error", message="No check result")
        except Exception as exc:
            logger.warning("Namecheap check failed for %s: %s", domain, exc)
            return DomainCheckResult(domain=domain, is_available=False, status="error", message=str(exc))

    def register_domain(
        self,
        domain: str,
        years: int = 1,
        contact_info: dict = None,
        nameservers: Optional[List[str]] = None
    ) -> DomainRegistrationResult:
        """Register domain via namecheap.domains.create."""
        contact_info = contact_info or {}
        params = {
            'DomainName': domain,
            'Years': str(years),
            # Standard registrant contact fields
            'RegistrantFirstName': contact_info.get('first_name', 'HostPro'),
            'RegistrantLastName': contact_info.get('last_name', 'Client'),
            'RegistrantAddress1': contact_info.get('address', 'Dhanmondi'),
            'RegistrantCity': contact_info.get('city', 'Dhaka'),
            'RegistrantStateProvince': contact_info.get('state', 'Dhaka'),
            'RegistrantPostalCode': contact_info.get('postal_code', '1205'),
            'RegistrantCountry': contact_info.get('country', 'BD'),
            'RegistrantPhone': contact_info.get('phone', '+880.1700000000'),
            'RegistrantEmailAddress': contact_info.get('email', 'admin@hostpro.bd'),
        }
        # Duplicate for Tech, Admin, AuxBilling
        for prefix in ['Tech', 'Admin', 'AuxBilling']:
            for k, v in list(params.items()):
                if k.startswith('Registrant'):
                    params[k.replace('Registrant', prefix)] = v

        if nameservers:
            params['Nameservers'] = ','.join(nameservers)

        try:
            root = self._call('namecheap.domains.create', params)
            ns = {'nc': 'http://api.namecheap.com/xml.response'}
            elem = root.find('.//nc:DomainCreateResult', ns)
            order_id = elem.attrib.get('OrderID', '') if elem is not None else ''
            return DomainRegistrationResult(
                success=True,
                domain=domain,
                order_id=order_id,
                message="Domain registered successfully on Namecheap!",
            )
        except Exception as exc:
            logger.error("Namecheap domain registration error: %s", exc)
            raise DomainRegistrationError(f"Could not register domain: {exc}")

    def renew_domain(self, domain: str, years: int = 1) -> DomainRegistrationResult:
        try:
            root = self._call('namecheap.domains.renew', {'DomainName': domain, 'Years': str(years)})
            return DomainRegistrationResult(success=True, domain=domain, message="Renewed successfully.")
        except Exception as exc:
            raise DomainRenewalError(f"Namecheap renewal failed: {exc}")

    def update_nameservers(self, domain: str, nameservers: List[str]) -> bool:
        parts = domain.split('.')
        sld = parts[0]
        tld = '.'.join(parts[1:])
        try:
            self._call('namecheap.domains.dns.setCustom', {
                'SLD': sld,
                'TLD': tld,
                'Nameservers': ','.join(nameservers),
            })
            return True
        except Exception:
            return False

    def get_domain_info(self, domain: str) -> dict:
        parts = domain.split('.')
        sld = parts[0]
        tld = '.'.join(parts[1:])
        root = self._call('namecheap.domains.getinfo', {'SLD': sld, 'TLD': tld})
        return {'status': 'active', 'raw': ET.tostring(root, encoding='unicode')}

    def get_account_balance(self) -> dict:
        try:
            root = self._call('namecheap.users.getBalances')
            ns = {'nc': 'http://api.namecheap.com/xml.response'}
            elem = root.find('.//nc:UserGetBalancesResult', ns)
            if elem is not None:
                return {
                    'balance': elem.attrib.get('AccountBalance', '0.00'),
                    'currency': elem.attrib.get('Currency', 'USD'),
                }
            return {'balance': '0.00', 'currency': 'USD'}
        except Exception as exc:
            return {'balance': '0.00', 'currency': 'USD', 'error': str(exc)}
