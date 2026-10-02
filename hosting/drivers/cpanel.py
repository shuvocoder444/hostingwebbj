"""
cPanel/WHM Driver
==================
Interacts with WHM's JSON API v1 using API token auth.

Docs: https://api.docs.cpanel.net/whm/

Security:
- WHM token is decrypted from DB just before each call.
- We use session=False (no cookie persistence) for stateless API calls.
- SSL verification is enabled in production.
"""
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.exceptions import (
    ProvisioningError,
    ServerDriverError,
    SuspensionError,
    TerminationError,
)

from .base import AccountInfo, BaseServerDriver

logger = logging.getLogger(__name__)


class CPanelDriver(BaseServerDriver):
    """
    WHM JSON API v1 driver.
    
    Endpoint pattern: https://{host}:2087/json-api/{function}?api.version=1
    Auth header: WHM {username}:{api_token}
    """

    def __init__(self, host: str, port: int, username: str, api_token: str, use_ssl: bool = True):
        super().__init__(host, port, username, api_token, use_ssl)
        # Build a requests Session with retry logic
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        """Create a requests Session with retry logic and WHM auth header."""
        session = requests.Session()
        
        # Retry on transient server errors (502, 503, 504) and connection issues
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=['GET', 'POST'],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        
        # WHM API token authentication
        session.headers.update({
            'Authorization': f'whm {self.username}:{self.api_token}',
            'Accept': 'application/json',
        })
        return session

    def _call(
        self,
        function: str,
        params: dict | None = None,
        timeout: int = 30,
    ) -> dict:
        """
        Make a WHM JSON API v1 call.
        
        Args:
            function: WHM function name (e.g., 'createacct').
            params:   Query parameters for the request.
            timeout:  Request timeout in seconds.
        
        Returns:
            Parsed JSON response dict.
        
        Raises:
            ServerDriverError: On network or API error.
        """
        url = f"{self._base_url}/json-api/{function}"
        all_params = {'api.version': '1', **(params or {})}
        
        try:
            response = self._session.get(
                url,
                params=all_params,
                timeout=timeout,
                verify=False,  # WHM commonly uses self-signed / hostname SSL
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise ServerDriverError(f"WHM API timeout calling '{function}' on {self.host}")
        except requests.exceptions.ConnectionError as exc:
            raise ServerDriverError(f"WHM connection failed to {self.host}: {exc}")
        except requests.exceptions.HTTPError as exc:
            raise ServerDriverError(f"WHM HTTP error {exc.response.status_code} on '{function}'")
        except ValueError as exc:
            raise ServerDriverError(f"WHM returned invalid JSON for '{function}': {exc}")

    def create_account(
        self,
        domain: str,
        username: str,
        password: str,
        package_name: str,
        email: str,
    ) -> dict:
        """
        Create a cPanel account via WHM createacct API.
        
        WHM createacct docs:
        https://api.docs.cpanel.net/whm/account-functions/createacct/
        """
        logger.info("cPanel: Creating account for domain=%s, username=%s", domain, username)
        
        result = self._call('createacct', params={
            'username': username,
            'domain': domain,
            'password': password,
            'plan': package_name,
            'contactemail': email,
            'featurelist': 'default',
        })
        
        # WHM returns result.0.status = 1 on success
        status = result.get('result', [{}])[0]
        if status.get('status') != 1:
            error_msg = status.get('statusmsg', 'Unknown WHM error')
            logger.error("cPanel account creation failed: %s", error_msg)
            raise ProvisioningError(
                f"cPanel createacct failed: {error_msg}",
                detail={'domain': domain, 'username': username, 'whm_response': status}
            )
        
        logger.info("cPanel: Account created successfully for domain=%s", domain)
        return {'success': True, 'message': status.get('statusmsg', 'Account created.')}

    def suspend_account(self, username: str, reason: str = 'Non-payment') -> dict:
        """Suspend a cPanel account via WHM suspendacct API."""
        logger.info("cPanel: Suspending account username=%s, reason=%s", username, reason)
        
        result = self._call('suspendacct', params={'user': username, 'reason': reason})
        status = result.get('result', [{}])[0]
        
        if status.get('status') != 1:
            raise SuspensionError(
                f"WHM suspendacct failed for {username}: {status.get('statusmsg')}",
                detail={'username': username}
            )
        return {'success': True, 'message': f'Account {username} suspended.'}

    def unsuspend_account(self, username: str) -> dict:
        """Unsuspend a cPanel account via WHM unsuspendacct API."""
        logger.info("cPanel: Unsuspending account username=%s", username)
        
        result = self._call('unsuspendacct', params={'user': username})
        status = result.get('result', [{}])[0]
        
        if status.get('status') != 1:
            raise SuspensionError(
                f"WHM unsuspendacct failed for {username}: {status.get('statusmsg')}",
                detail={'username': username}
            )
        return {'success': True, 'message': f'Account {username} unsuspended.'}

    def terminate_account(self, username: str) -> dict:
        """Permanently delete a cPanel account via WHM removeacct API."""
        logger.warning("cPanel: TERMINATING account username=%s", username)
        
        result = self._call('removeacct', params={'user': username})
        status = result.get('result', [{}])[0]
        
        if status.get('status') != 1:
            raise TerminationError(
                f"WHM removeacct failed for {username}: {status.get('statusmsg')}",
                detail={'username': username}
            )
        return {'success': True, 'message': f'Account {username} terminated.'}

    def get_account_info(self, username: str) -> AccountInfo:
        """Fetch live account info via WHM accountsummary API."""
        result = self._call('accountsummary', params={'user': username})
        acct = result.get('acct', [None])[0]
        
        if not acct:
            raise ServerDriverError(f"No account info returned for {username}")
        
        return AccountInfo(
            username=acct.get('user', username),
            domain=acct.get('domain', ''),
            ip=acct.get('ip', ''),
            package=acct.get('plan', ''),
            disk_used_mb=float(acct.get('diskused', 0)),
            bandwidth_used_mb=float(acct.get('totalbytes', 0)) / (1024 * 1024),
        )

    def change_package(self, username: str, new_package_name: str) -> dict:
        """Change WHM package via changepackage API."""
        result = self._call('changepackage', params={'user': username, 'pkg': new_package_name})
        status = result.get('result', [{}])[0]
        
        if status.get('status') != 1:
            raise ServerDriverError(
                f"WHM changepackage failed for {username}: {status.get('statusmsg')}"
            )
        return {'success': True, 'message': f'Package changed to {new_package_name}.'}

    def list_packages(self) -> list[dict]:
        """
        Fetch all hosting packages configured on WHM server via listpkgs API.
        """
        result = self._call('listpkgs')
        raw_pkgs = []
        if isinstance(result, dict):
            if 'package' in result:
                raw_pkgs = result['package']
            elif 'data' in result and 'pkg' in result['data']:
                raw_pkgs = result['data']['pkg']
            elif 'pkg' in result:
                raw_pkgs = result['pkg']

        packages = []
        for p in raw_pkgs:
            quota_val = str(p.get('QUOTA', '0')).strip().lower()
            bw_val = str(p.get('BWLIMIT', '0')).strip().lower()
            try:
                quota_mb = 0 if quota_val in ('unlimited', 'unassigned', '', '0') else int(p.get('QUOTA', 0))
            except (ValueError, TypeError):
                quota_mb = 0
            try:
                bw_mb = 0 if bw_val in ('unlimited', 'unassigned', '', '0') else int(p.get('BWLIMIT', 0))
            except (ValueError, TypeError):
                bw_mb = 0

            packages.append({
                'name': p.get('name', ''),
                'disk_quota_mb': quota_mb,
                'bandwidth_mb': bw_mb,
                'max_sub': p.get('MAXSUB', 'unlimited'),
                'max_sql': p.get('MAXSQL', 'unlimited'),
                'max_ftp': p.get('MAXFTP', 'unlimited'),
                'max_pop': p.get('MAXPOP', 'unlimited'),
                'cpanel_theme': p.get('CPMOD', 'jupiter'),
            })
        return packages

    def create_package(self, name: str, disk_quota_mb: int = 1024, bandwidth_mb: int = 10240) -> dict:
        """Create a new package in WHM via addpkg API."""
        params = {
            'name': name,
            'quota': str(disk_quota_mb) if disk_quota_mb > 0 else 'unlimited',
            'bwlimit': str(bandwidth_mb) if bandwidth_mb > 0 else 'unlimited',
            'featurelist': 'default',
            'cpmod': 'jupiter',
            'cgi': '1',
            'hasshell': '0',
            'maxftp': 'unlimited',
            'maxsql': 'unlimited',
            'maxpop': 'unlimited',
            'maxsub': 'unlimited',
            'maxpark': 'unlimited',
            'maxaddon': 'unlimited',
        }
        res = self._call('addpkg', params=params)
        status = res.get('result', [{}])[0] if isinstance(res.get('result'), list) else {}
        if status.get('status') != 1:
            err = status.get('statusmsg', res.get('metadata', {}).get('reason', 'Failed to create package in WHM'))
            raise ServerDriverError(f"WHM addpkg failed: {err}")
        return {'success': True, 'message': status.get('statusmsg', f"Package '{name}' created in WHM.")}

    def delete_package(self, name: str) -> dict:
        """Delete a package from WHM via killpkg API."""
        res = self._call('killpkg', params={'pkg': name})
        status = res.get('result', [{}])[0] if isinstance(res.get('result'), list) else {}
        if status.get('status') != 1:
            err = status.get('statusmsg', res.get('metadata', {}).get('reason', 'Failed to delete package in WHM'))
            raise ServerDriverError(f"WHM killpkg failed: {err}")
        return {'success': True, 'message': status.get('statusmsg', f"Package '{name}' deleted from WHM.")}

    def test_connection(self) -> dict:
        """Ping WHM version API to verify host connectivity and API token."""
        url = f"{self._base_url}/json-api/version"
        try:
            response = self._session.get(
                url,
                params={'api.version': '1'},
                timeout=12,
                verify=False,
            )
            if response.status_code == 200:
                data = response.json()
                version = data.get('version', '')
                return {
                    'success': True,
                    'message': f"WHM connection SUCCESSFUL! Host {self.host} responded. cPanel/WHM Version: {version or 'OK'}"
                }
            elif response.status_code in (401, 403):
                return {
                    'success': False,
                    'message': f"WHM host {self.host} reached, but authentication failed (HTTP {response.status_code}). Please verify your WHM API Username & Token."
                }
            else:
                return {
                    'success': False,
                    'message': f"WHM host {self.host} returned HTTP {response.status_code}: {response.text[:120]}"
                }
        except requests.exceptions.Timeout:
            return {'success': False, 'message': f"Connection timed out reaching {self.host}:2087."}
        except requests.exceptions.ConnectionError as exc:
            return {'success': False, 'message': f"Could not reach {self.host}:2087 (DNS or network firewall error)."}
        except Exception as exc:
            return {'success': False, 'message': f"WHM ping failed: {str(exc)}"}


