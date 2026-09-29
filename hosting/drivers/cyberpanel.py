"""
CyberPanel Driver
==================
Interacts with CyberPanel's REST API.

Docs: https://cyberpanel.net/docs/
Auth: admin username + password in POST body.
"""
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.exceptions import ProvisioningError, SuspensionError, TerminationError, ServerDriverError
from .base import BaseServerDriver, AccountInfo

logger = logging.getLogger(__name__)


class CyberPanelDriver(BaseServerDriver):
    """
    CyberPanel REST API driver.

    Endpoint: https://{host}:8090/api/{action}
    Auth: adminUser + adminPass in POST body.
    """

    def __init__(self, host: str, port: int, username: str, api_token: str, use_ssl: bool = True):
        super().__init__(host, port, username, api_token, use_ssl)
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
        session.headers.update({'Content-Type': 'application/json'})
        return session

    def _call(self, endpoint: str, payload: dict, timeout: int = 30) -> dict:
        """POST to a CyberPanel endpoint with admin credentials injected."""
        url = f"{self._base_url}/api/{endpoint}"
        # CyberPanel requires credentials in every request body
        payload.update({
            'adminUser': self.username,
            'adminPass': self.api_token,  # api_token holds admin password
        })

        try:
            response = self._session.post(
                url, json=payload, timeout=timeout, verify=self.use_ssl
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise ServerDriverError(
                f"CyberPanel API timeout calling '{endpoint}' on {self.host}"
            )
        except requests.exceptions.ConnectionError as exc:
            raise ServerDriverError(
                f"CyberPanel connection failed to {self.host}: {exc}"
            )
        except requests.exceptions.HTTPError as exc:
            raise ServerDriverError(
                f"CyberPanel HTTP error {exc.response.status_code} on '{endpoint}'"
            )
        except ValueError as exc:
            raise ServerDriverError(
                f"CyberPanel returned invalid JSON for '{endpoint}': {exc}"
            )

    def create_account(
        self,
        domain: str,
        username: str,
        password: str,
        package_name: str,
        email: str,
    ) -> dict:
        """Create a website on CyberPanel via /api/createWebsite."""
        logger.info("CyberPanel: Creating website domain=%s", domain)

        result = self._call('createWebsite', {
            'domainName': domain,
            'ownerEmail': email,
            'websiteOwner': email,   # CyberPanel uses email as owner identifier
            'ownerPassword': password,
            'packageName': package_name,
            'acl': 'user',
        })

        # CyberPanel returns {"createWebSiteStatus": 1, "error_message": "None"}
        if result.get('createWebSiteStatus') != 1:
            error_msg = result.get('error_message', 'Unknown error')
            logger.error("CyberPanel createWebsite failed: %s", error_msg)
            raise ProvisioningError(
                f"CyberPanel createWebsite failed: {error_msg}",
                detail={'domain': domain, 'cyberpanel_response': result}
            )

        return {'success': True, 'message': f'Website {domain} created.'}

    def suspend_account(self, username: str, reason: str = '') -> dict:
        """Suspend via CyberPanel /api/suspendWebsite."""
        result = self._call('suspendWebsite', {'websiteName': username})
        if result.get('websiteSuspendStatus') != 1:
            raise SuspensionError(
                f"CyberPanel suspend failed for {username}: {result.get('error_message')}",
                detail={'username': username}
            )
        return {'success': True, 'message': f'{username} suspended.'}

    def unsuspend_account(self, username: str) -> dict:
        """Unsuspend via CyberPanel /api/unsuspendWebsite."""
        result = self._call('unsuspendWebsite', {'websiteName': username})
        if result.get('websiteUnsuspendStatus') != 1:
            raise SuspensionError(
                f"CyberPanel unsuspend failed for {username}: {result.get('error_message')}",
                detail={'username': username}
            )
        return {'success': True, 'message': f'{username} unsuspended.'}

    def terminate_account(self, username: str) -> dict:
        """Delete a website via CyberPanel /api/deleteWebsite."""
        logger.warning("CyberPanel: DELETING website username=%s", username)
        result = self._call('deleteWebsite', {'websiteName': username})
        if result.get('deleteWebsiteStatus') != 1:
            raise TerminationError(
                f"CyberPanel deleteWebsite failed for {username}: {result.get('error_message')}",
                detail={'username': username}
            )
        return {'success': True, 'message': f'{username} deleted.'}

    def get_account_info(self, username: str) -> AccountInfo:
        """Fetch stats via CyberPanel /api/getWebsiteStats."""
        result = self._call('getWebsiteStats', {'domainName': username})
        return AccountInfo(
            username=username,
            domain=username,
            ip='',  # CyberPanel doesn't return IP from this endpoint
            package=result.get('packageName', ''),
            disk_used_mb=float(result.get('diskUsed', 0)),
            bandwidth_used_mb=float(result.get('bandwidthUsed', 0)),
        )

    def change_package(self, username: str, new_package_name: str) -> dict:
        """Change package via CyberPanel /api/changePackage."""
        result = self._call('changePackage', {
            'domainName': username,
            'packageName': new_package_name,
        })
        if result.get('changePackageStatus') != 1:
            raise ServerDriverError(
                f"CyberPanel changePackage failed for {username}: {result.get('error_message')}"
            )
        return {'success': True, 'message': f'Package changed to {new_package_name}.'}
