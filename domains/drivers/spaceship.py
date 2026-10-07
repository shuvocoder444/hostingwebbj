"""
Spaceship.com API Domain Registrar Driver
==========================================
Full integration with Spaceship External API v1 (Namecheap Cloud Platform).
Based on official Spaceship OpenAPI 3.0.0 Specification.

Authentication:
  - X-API-Key: Spaceship API Key (self.api_user)
  - X-API-Secret: Spaceship API Secret (self.api_key)

Endpoints:
  - Base: https://spaceship.dev/api (Live) / https://sandbox.spaceship.dev/api (Sandbox)
  - Domain Availability: GET /v1/domains/{domain}/available, POST /v1/domains/available
  - Domain List: GET /v1/domains
  - Domain Details: GET /v1/domains/{domain}
  - Domain Registration: POST /v1/domains/{domain} (202 Accepted Async)
  - Domain Renewal: POST /v1/domains/{domain}/renew (202 Accepted Async)
  - Nameservers: PUT /v1/domains/{domain}/nameservers
  - Contacts: PUT /v1/contacts, GET /v1/contacts/{contact}
  - DNS Records: GET / PUT / DELETE /v1/dns/records/{domain}
  - Auth Code & Transfer Lock: GET /v1/domains/{domain}/transfer/auth-code, PUT /v1/domains/{domain}/transfer/lock
  - Auto-renewal & Privacy: PUT /v1/domains/{domain}/autorenew, PUT /v1/domains/{domain}/privacy/preference
  - Async Operations: GET /v1/async-operations/{operationId}
"""

import logging
import re
from decimal import Decimal
from typing import Any

import requests

from core.exceptions import ServerDriverError

from .base import BaseRegistrarDriver, DomainCheckResult, DomainRegistrationResult

logger = logging.getLogger('domains')


class SpaceshipDriver(BaseRegistrarDriver):
    """
    Spaceship.com Domain Registrar Driver.
    """

    LIVE_BASE_URL = "https://spaceship.dev/api"
    SANDBOX_BASE_URL = "https://sandbox.spaceship.dev/api"

    def __init__(self, api_user: str, api_key: str, is_sandbox: bool = False, extra_config: dict = None):
        super().__init__(api_user, api_key, is_sandbox, extra_config)
        endpoint = self.extra_config.get('api_endpoint')
        if not endpoint:
            endpoint = self.SANDBOX_BASE_URL if self.is_sandbox else self.LIVE_BASE_URL
        endpoint = endpoint.rstrip('/')
        endpoint = endpoint.removesuffix('/v1')
        if not endpoint.endswith('/api') and 'spaceship.dev' in endpoint:
            endpoint = f"{endpoint}/api"
        self.base_url = endpoint

    def _get_headers(self) -> dict:
        return {
            'X-API-Key': str(self.api_user).strip(),
            'X-API-Secret': str(self.api_key).strip(),
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _call(
        self,
        path: str,
        method: str = 'GET',
        params: dict | None = None,
        json_data: Any | None = None,
        timeout: int = 30
    ) -> dict | list:
        """
        Execute an authenticated HTTP request to Spaceship API.
        """
        clean_path = path if path.startswith('/') else f"/{path}"
        if not clean_path.startswith('/v1/'):
            clean_path = f"/v1{clean_path}"
        url = f"{self.base_url}{clean_path}"
        headers = self._get_headers()

        try:
            req_kwargs = {
                'headers': headers,
                'timeout': timeout,
            }
            if params:
                req_kwargs['params'] = params
            if json_data is not None:
                req_kwargs['json'] = json_data

            resp = requests.request(method.upper(), url, **req_kwargs)

            # 204 No Content
            if resp.status_code == 204:
                return {}

            # Parse JSON if present
            try:
                res_data = resp.json() if resp.content else {}
            except Exception:
                res_data = {'raw_text': resp.text}

            # If 202 Accepted (Async operation created), inject async operation id
            if resp.status_code == 202:
                op_id = resp.headers.get('spaceship-async-operationid') or resp.headers.get('Spaceship-Async-OperationId')
                if isinstance(res_data, dict):
                    res_data['async_operation_id'] = op_id
                    res_data['status'] = 'accepted'
                return res_data

            if resp.status_code >= 400:
                err_msg = ""
                if isinstance(res_data, dict):
                    err_msg = res_data.get('detail') or res_data.get('message') or res_data.get('error')
                    if not err_msg and 'data' in res_data and isinstance(res_data['data'], list):
                        details = [d.get('details') or d.get('field') for d in res_data['data'] if isinstance(d, dict)]
                        err_msg = ", ".join(filter(None, details))
                if not err_msg:
                    err_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                raise ServerDriverError(f"Spaceship API Error ({resp.status_code}): {err_msg}")

            return res_data

        except requests.exceptions.RequestException as e:
            logger.error("Spaceship request error (%s %s): %s", method, url, e)
            raise ServerDriverError(f"Connection to Spaceship API failed: {e!s}")

    def check_availability(self, domain: str) -> DomainCheckResult:
        """
        Check if a single domain is available for registration via Spaceship API.
        GET /v1/domains/{domain}/available
        """
        clean_domain = domain.strip().lower()
        try:
            res = self._call(f"/domains/{clean_domain}/available", method='GET')
            if isinstance(res, dict):
                result_status = res.get('result', '')
                is_available = (result_status == 'available')
                price = None
                currency = 'USD'
                is_premium = False

                for p in res.get('premiumPricing', []):
                    if p.get('operation') == 'register':
                        try:
                            price = Decimal(str(p.get('price', '0.00')))
                            currency = p.get('currency', 'USD')
                            is_premium = True
                        except Exception:
                            pass

                return DomainCheckResult(
                    domain=clean_domain,
                    is_available=is_available,
                    status=result_status,
                    price=price,
                    currency=currency,
                    is_premium=is_premium,
                    message=f"Spaceship: {result_status.capitalize()}"
                )
        except Exception as e:
            logger.warning("Spaceship single domain availability check failed for %s (%s). Falling back to WHOIS.", clean_domain, e)

        # Fallback to live WHOIS / DNS lookup if API is unavailable or rate limited
        from domains.whois_checker import check_domain_live
        lookup = check_domain_live(clean_domain)
        return DomainCheckResult(
            domain=clean_domain,
            is_available=lookup.is_available,
            status=lookup.status,
            price=None,
            currency='USD',
            message=lookup.message
        )

    def check_domains_batch(self, domains: list[str]) -> list[DomainCheckResult]:
        """
        Check availability for up to 20 domains in batch.
        POST /v1/domains/available
        """
        clean_domains = [d.strip().lower() for d in domains if d.strip()][:20]
        if not clean_domains:
            return []

        try:
            res = self._call("/domains/available", method='POST', json_data={"domains": clean_domains})
            results = []
            if isinstance(res, dict) and 'domains' in res:
                for item in res['domains']:
                    d_name = item.get('domain', '')
                    r_status = item.get('result', '')
                    results.append(DomainCheckResult(
                        domain=d_name,
                        is_available=(r_status == 'available'),
                        status=r_status,
                        currency='USD',
                        message=f"Spaceship: {r_status}"
                    ))
                return results
        except Exception as e:
            logger.error("Spaceship batch check failed: %s", e)

        return [self.check_availability(d) for d in clean_domains]

    def list_domains(self) -> list[dict]:
        """
        Fetch all registered domains under this Spaceship account.
        GET /v1/domains?take=100&skip=0&orderBy=name
        """
        all_domains = []
        skip = 0
        take = 100

        while True:
            try:
                res = self._call("/domains", method='GET', params={
                    'take': take,
                    'skip': skip,
                    'orderBy': 'name'
                })
                if not isinstance(res, dict):
                    break

                items = res.get('items', [])
                total = res.get('total', 0)

                for item in items:
                    name = item.get('name') or item.get('unicodeName', '')
                    reg_date = item.get('registrationDate', '')
                    exp_date = item.get('expirationDate', '')
                    lifecycle = (item.get('lifecycleStatus') or 'registered').lower()
                    
                    # Normalize lifecycle status to HostPro standard
                    status = 'active'
                    if lifecycle in ('grace1', 'grace2', 'redemption', 'expired'):
                        status = 'suspended'
                    elif lifecycle == 'creating':
                        status = 'pending'

                    ns_data = item.get('nameservers', {})
                    hosts = ns_data.get('hosts', []) if isinstance(ns_data, dict) else []

                    all_domains.append({
                        'domain': name,
                        'domainname': name,
                        'name': name,
                        'unicode_name': item.get('unicodeName', name),
                        'status': status,
                        'lifecycle_status': lifecycle,
                        'registration_date': reg_date[:10] if reg_date else '',
                        'expiry_date': exp_date[:10] if exp_date else '',
                        'expires_at': exp_date[:10] if exp_date else '',
                        'nextduedate': exp_date[:10] if exp_date else '',
                        'auto_renew': item.get('autoRenew', False),
                        'is_premium': item.get('isPremium', False),
                        'nameservers': hosts,
                        'raw': item,
                    })

                skip += len(items)
                if skip >= total or not items:
                    break

            except Exception as e:
                logger.error("Spaceship list_domains error at skip=%d: %s", skip, e)
                if not all_domains:
                    raise ServerDriverError(f"Spaceship list_domains failed: {e!s}")
                break

        return all_domains

    def get_domain_info(self, domain: str) -> dict:
        """
        Get details of a specific domain.
        GET /v1/domains/{domain}
        """
        clean_domain = domain.strip().lower()
        res = self._call(f"/domains/{clean_domain}", method='GET')
        if isinstance(res, dict):
            return res
        return {'data': res}

    def _format_phone(self, phone: str, country: str = 'BD') -> str:
        """
        Spaceship phone format pattern: ^\\+\\d{1,3}\\.\\d{4,}$
        Example: +880.1712345678 or +1.8005550199
        """
        if not phone:
            return "+880.1711000000" if country == 'BD' else "+1.8005550199"

        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        if not cleaned.startswith('+'):
            if country == 'BD':
                if cleaned.startswith('880'):
                    cleaned = f"+{cleaned}"
                elif cleaned.startswith('01'):
                    cleaned = f"+880.{cleaned[1:]}"
                else:
                    cleaned = f"+880.{cleaned}"
            elif country == 'US':
                cleaned = f"+1.{cleaned}"
            else:
                cleaned = f"+880.{cleaned}"

        if '.' not in cleaned:
            match = re.match(r'^\+(\d{1,3})(\d{4,})$', cleaned)
            if match:
                cleaned = f"+{match.group(1)}.{match.group(2)}"
            else:
                cleaned = "+880.1711000000"

        return cleaned

    def save_contact(self, contact_info: dict) -> str:
        """
        Save contact details and return generated contactId.
        PUT /v1/contacts
        """
        first_name = contact_info.get('first_name') or contact_info.get('firstName') or 'Host'
        last_name = contact_info.get('last_name') or contact_info.get('lastName') or 'Customer'
        email = contact_info.get('email') or 'admin@webkoders.com'
        org = contact_info.get('organization') or contact_info.get('company_name') or 'WebKoders'
        addr1 = contact_info.get('address1') or contact_info.get('address_line1') or 'Road 1, Block A'
        addr2 = contact_info.get('address2') or contact_info.get('address_line2') or ''
        city = contact_info.get('city') or 'Dhaka'
        country = (contact_info.get('country') or 'BD').upper()[:2]
        state = contact_info.get('state') or contact_info.get('stateProvince') or 'Dhaka'
        postal_code = contact_info.get('postal_code') or contact_info.get('postalCode') or '1200'
        phone = self._format_phone(contact_info.get('phone', ''), country=country)

        payload = {
            'firstName': first_name,
            'lastName': last_name,
            'organization': org,
            'email': email,
            'address1': addr1,
            'address2': addr2,
            'city': city,
            'country': country,
            'stateProvince': state,
            'postalCode': postal_code,
            'phone': phone,
        }

        res = self._call('/contacts', method='PUT', json_data=payload)
        if isinstance(res, dict) and 'contactId' in res:
            return res['contactId']
        raise ServerDriverError(f"Spaceship did not return contactId: {res}")

    def register_domain(
        self,
        domain: str,
        years: int = 1,
        contact_info: dict | None = None,
        nameservers: list[str] | None = None
    ) -> DomainRegistrationResult:
        """
        Register a specific domain on Spaceship.com.
        POST /v1/domains/{domain} (Async 202 Accepted)
        """
        clean_domain = domain.strip().lower()
        contact_id = None

        if contact_info:
            try:
                contact_id = self.save_contact(contact_info)
            except Exception as e:
                logger.warning("Spaceship save_contact error (%s). Using fallback contact.", e)

        if not contact_id:
            contact_id = self.save_contact({
                'first_name': 'Domain',
                'last_name': 'Manager',
                'email': self.api_user if '@' in str(self.api_user) else 'domains@webkoders.com',
                'organization': 'HostPro',
                'address1': 'House 12, Road 4',
                'city': 'Dhaka',
                'country': 'BD',
                'state': 'Dhaka',
                'postal_code': '1212',
                'phone': '+880.1711000000'
            })

        payload = {
            'autoRenew': False,
            'years': max(1, int(years)),
            'privacyProtection': {
                'level': 'high',
                'userConsent': True
            },
            'contacts': {
                'registrant': contact_id,
                'admin': contact_id,
                'tech': contact_id,
                'billing': contact_id
            }
        }

        try:
            res = self._call(f"/domains/{clean_domain}", method='POST', json_data=payload)
            op_id = res.get('async_operation_id', '') if isinstance(res, dict) else ''

            if nameservers:
                try:
                    self.update_nameservers(clean_domain, nameservers)
                except Exception as ns_err:
                    logger.warning("Spaceship nameservers update note for %s: %s", clean_domain, ns_err)

            return DomainRegistrationResult(
                success=True,
                domain=clean_domain,
                order_id=op_id,
                message=f"Spaceship registration order submitted successfully (Operation ID: {op_id}).",
                raw_response=res if isinstance(res, dict) else {'data': res}
            )
        except Exception as exc:
            logger.error("Spaceship register_domain error for %s: %s", clean_domain, exc)
            return DomainRegistrationResult(
                success=False,
                domain=clean_domain,
                message=str(exc),
                raw_response={'error': str(exc)}
            )

    def renew_domain(self, domain: str, years: int = 1) -> DomainRegistrationResult:
        """
        Request domain renewal.
        POST /v1/domains/{domain}/renew (Async 202 Accepted)
        """
        clean_domain = domain.strip().lower()
        try:
            info = self.get_domain_info(clean_domain)
            current_exp = info.get('expirationDate')
            if not current_exp:
                current_exp = "2026-01-01T00:00:00.000Z"

            payload = {
                'years': max(1, int(years)),
                'currentExpirationDate': current_exp
            }

            res = self._call(f"/domains/{clean_domain}/renew", method='POST', json_data=payload)
            op_id = res.get('async_operation_id', '') if isinstance(res, dict) else ''

            return DomainRegistrationResult(
                success=True,
                domain=clean_domain,
                order_id=op_id,
                message=f"Spaceship renewal order submitted (Operation ID: {op_id}).",
                raw_response=res if isinstance(res, dict) else {'data': res}
            )
        except Exception as exc:
            logger.error("Spaceship renew_domain error for %s: %s", clean_domain, exc)
            return DomainRegistrationResult(
                success=False,
                domain=clean_domain,
                message=str(exc),
                raw_response={'error': str(exc)}
            )

    def update_nameservers(self, domain: str, nameservers: list[str]) -> bool:
        """
        Update nameservers for a domain.
        PUT /v1/domains/{domain}/nameservers
        """
        clean_domain = domain.strip().lower()
        clean_ns = [ns.strip() for ns in nameservers if ns and ns.strip()]

        if clean_ns:
            payload = {
                'provider': 'custom',
                'hosts': clean_ns
            }
        else:
            payload = {
                'provider': 'basic'
            }

        try:
            self._call(f"/domains/{clean_domain}/nameservers", method='PUT', json_data=payload)
            return True
        except Exception as exc:
            logger.error("Spaceship update_nameservers failed for %s: %s", clean_domain, exc)
            return False

    def get_nameservers(self, domain: str) -> list[str]:
        """
        Get current nameservers for a domain.
        """
        info = self.get_domain_info(domain)
        ns_data = info.get('nameservers', {})
        if isinstance(ns_data, dict):
            return ns_data.get('hosts', [])
        return []

    def get_auth_code(self, domain: str) -> dict:
        """
        Get domain EPP / Auth code.
        GET /v1/domains/{domain}/transfer/auth-code
        """
        clean_domain = domain.strip().lower()
        res = self._call(f"/domains/{clean_domain}/transfer/auth-code", method='GET')
        if isinstance(res, dict):
            return res
        return {'authCode': str(res)}

    def set_transfer_lock(self, domain: str, is_locked: bool = True) -> bool:
        """
        Update domain transfer lock.
        PUT /v1/domains/{domain}/transfer/lock
        """
        clean_domain = domain.strip().lower()
        try:
            self._call(f"/domains/{clean_domain}/transfer/lock", method='PUT', json_data={'isLocked': is_locked})
            return True
        except Exception as exc:
            logger.error("Spaceship set_transfer_lock failed for %s: %s", clean_domain, exc)
            return False

    def set_autorenew(self, domain: str, is_enabled: bool = True) -> bool:
        """
        Update domain autorenewal state.
        PUT /v1/domains/{domain}/autorenew
        """
        clean_domain = domain.strip().lower()
        try:
            self._call(f"/domains/{clean_domain}/autorenew", method='PUT', json_data={'isEnabled': is_enabled})
            return True
        except Exception as exc:
            logger.error("Spaceship set_autorenew failed for %s: %s", clean_domain, exc)
            return False

    def set_privacy_protection(self, domain: str, level: str = 'high') -> bool:
        """
        Update domain privacy preference.
        PUT /v1/domains/{domain}/privacy/preference
        """
        clean_domain = domain.strip().lower()
        try:
            self._call(
                f"/domains/{clean_domain}/privacy/preference",
                method='PUT',
                json_data={'privacyLevel': level, 'userConsent': True}
            )
            return True
        except Exception as exc:
            logger.error("Spaceship set_privacy_protection failed for %s: %s", clean_domain, exc)
            return False

    def get_dns_records(self, domain: str) -> list[dict]:
        """
        Get domain DNS resource records list.
        GET /v1/dns/records/{domain}
        """
        clean_domain = domain.strip().lower()
        res = self._call(f"/dns/records/{clean_domain}", method='GET', params={'take': 500, 'skip': 0})
        if isinstance(res, dict) and 'items' in res:
            return res['items']
        return []

    def save_dns_records(self, domain: str, records: list[dict], force: bool = True) -> bool:
        """
        Save custom DNS resource records.
        PUT /v1/dns/records/{domain}
        """
        clean_domain = domain.strip().lower()
        try:
            self._call(
                f"/dns/records/{clean_domain}",
                method='PUT',
                json_data={'force': force, 'items': records}
            )
            return True
        except Exception as exc:
            logger.error("Spaceship save_dns_records failed for %s: %s", clean_domain, exc)
            return False

    def delete_dns_records(self, domain: str, records: list[dict]) -> bool:
        """
        Delete custom DNS resource records.
        DELETE /v1/dns/records/{domain}
        """
        clean_domain = domain.strip().lower()
        try:
            self._call(f"/dns/records/{clean_domain}", method='DELETE', json_data=records)
            return True
        except Exception as exc:
            logger.error("Spaceship delete_dns_records failed for %s: %s", clean_domain, exc)
            return False

    def get_async_operation(self, operation_id: str) -> dict:
        """
        Obtain async operation details (pending / success / failed).
        GET /v1/async-operations/{operationId}
        """
        return self._call(f"/async-operations/{operation_id}", method='GET')

    def get_account_balance(self) -> dict:
        """
        Check account connection status with Spaceship.
        """
        try:
            res = self._call("/domains", method='GET', params={'take': 1, 'skip': 0})
            total = res.get('total', 0) if isinstance(res, dict) else 0
            return {
                'balance': 'Connected',
                'currency': 'USD',
                'domains_count': total,
                'status': 'active',
                'message': f'Spaceship API Connected ({total} domain(s) active)'
            }
        except Exception as e:
            return {
                'balance': 'N/A',
                'currency': 'USD',
                'status': 'error',
                'message': str(e)
            }
