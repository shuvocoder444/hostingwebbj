"""
Google OAuth 2.0 & Social Sign-In Module
=========================================
Handles frictionless 1-Click Login & Registration with Google / Gmail:
- Standard OAuth 2.0 Authorization Code flow (Desktop, Mobile, WebViews)
- Google Identity Services (One Tap & Credential API)
- Automatic account provisioning for new clients (bypasses manual OTP because Google pre-verifies emails)
- Seamless preservation of 'next' checkout/dashboard redirect URLs
"""
import json
import logging
import secrets
import urllib.parse
import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import ClientProfile
from core.models import SiteSetting

User = get_user_model()
logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def get_google_config(request):
    """
    Retrieve Google OAuth client credentials and dynamic callback redirect URI.
    Allows configuration via both Django Admin (SiteSetting) and environment (.env).
    """
    site = SiteSetting.get_settings()
    client_id = site.get_google_client_id() if hasattr(site, 'get_google_client_id') else getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = site.get_google_client_secret() if hasattr(site, 'get_google_client_secret') else getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    enabled = getattr(site, 'enable_google_login', True)

    host = request.get_host()
    # Support HTTPS detection behind Nginx / Cloudflare / Phusion Passenger proxies
    scheme = 'https' if request.is_secure() or 'velohoster.com' in host or request.META.get('HTTP_X_FORWARDED_PROTO') == 'https' else 'http'
    redirect_uri = f"{scheme}://{host}/accounts/google/callback/"

    return {
        'enabled': enabled,
        'client_id': (client_id or '').strip(),
        'client_secret': (client_secret or '').strip(),
        'redirect_uri': redirect_uri,
    }


def google_login_redirect_view(request):
    """
    Initiate Google OAuth2 flow.
    Saves next URL and anti-CSRF state token in session, then redirects to Google.
    """
    config = get_google_config(request)
    if not config['enabled']:
        messages.error(request, "Google sign-in is currently disabled.")
        return redirect('login')

    if not config['client_id']:
        messages.warning(
            request,
            "Google Login is not configured yet. Please configure the Google Client ID & Secret in Admin Settings."
        )
        return redirect('login')

    # Preserve destination next URL
    next_url = request.GET.get('next') or request.POST.get('next') or '/dashboard/'
    if 'google' in next_url:
        next_url = '/dashboard/'
    request.session['google_oauth_next'] = next_url

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session['google_oauth_state'] = state

    params = {
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)


def google_login_callback_view(request):
    """
    Handle Google OAuth2 callback redirect.
    Validates state, exchanges authorization code for tokens, extracts Gmail profile,
    registers new customer or logs in existing customer, and redirects to destination.
    """
    config = get_google_config(request)
    next_url = request.session.pop('google_oauth_next', '/dashboard/')
    expected_state = request.session.pop('google_oauth_state', None)

    # 1. Check for cancellation or error returned by Google
    error = request.GET.get('error')
    if error:
        logger.warning("Google login cancelled or error: %s", error)
        messages.info(request, "Google sign-in was cancelled.")
        return redirect('login')

    code = request.GET.get('code')
    state = request.GET.get('state')

    # 2. State & code validation
    if not code or not state or state != expected_state:
        logger.warning("Google OAuth state mismatch: received '%s', expected '%s'", state, expected_state)
        messages.error(request, "Authentication session expired or security verification failed. Please try again.")
        return redirect('login')

    if not config['client_secret']:
        messages.error(request, "Google Client Secret is missing in server settings.")
        return redirect('login')

    # 3. Exchange authorization code for access token
    try:
        token_resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'code': code,
                'client_id': config['client_id'],
                'client_secret': config['client_secret'],
                'redirect_uri': config['redirect_uri'],
                'grant_type': 'authorization_code',
            },
            timeout=12,
        )
        token_data = token_resp.json()
    except Exception as exc:
        logger.exception("Failed to exchange Google OAuth code: %s", exc)
        messages.error(request, "Failed to connect to Google authentication service. Please check your internet connection.")
        return redirect('login')

    access_token = token_data.get('access_token')
    if not access_token:
        err_msg = token_data.get('error_description') or token_data.get('error') or 'Token exchange failed'
        logger.error("Google token error response: %s", token_data)
        messages.error(request, f"Google authentication failed: {err_msg}")
        return redirect('login')

    # 4. Fetch verified Gmail profile from Google userinfo API
    try:
        userinfo_resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        profile_data = userinfo_resp.json()
    except Exception as exc:
        logger.exception("Failed to fetch Google userinfo: %s", exc)
        messages.error(request, "Could not fetch profile details from Google.")
        return redirect('login')

    email = (profile_data.get('email') or '').strip().lower()
    if not email:
        messages.error(request, "Google did not provide an email address for your account.")
        return redirect('login')

    given_name = (profile_data.get('given_name') or profile_data.get('name') or email.split('@')[0]).strip()
    family_name = (profile_data.get('family_name') or '').strip()

    # 5. Find existing customer or register new customer automatically
    user = User.objects.filter(email__iexact=email).first()
    is_new_user = False

    if not user:
        is_new_user = True
        random_password = secrets.token_urlsafe(32)
        user = User.objects.create_user(
            email=email,
            first_name=given_name,
            last_name=family_name or 'Client',
            role=User.Role.CLIENT,
            is_active=True,
            password=random_password,
        )
        ClientProfile.objects.create(
            user=user,
            is_email_verified=True,
            country='BD',
            currency=request.session.get('currency', 'BDT'),
        )
        logger.info("New client account automatically registered via Google Sign-In: %s", email)
    else:
        # Existing account: update email verification status if needed
        if hasattr(user, 'profile'):
            if not user.profile.is_email_verified:
                user.profile.is_email_verified = True
                user.profile.save(update_fields=['is_email_verified'])
        if not user.is_active:
            messages.error(request, "Your account has been deactivated. Please contact customer support.")
            return redirect('login')

    # 6. Authenticate and start session
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    if is_new_user:
        messages.success(request, f"Welcome to VeloHoster, {user.first_name}! Your account has been registered with Google.")
    else:
        messages.success(request, f"Welcome back, {user.first_name}!")

    # 7. Set JWT cookie for client-side API calls
    try:
        refresh = RefreshToken.for_user(user)
        response = redirect(next_url)
        response.set_cookie('access_token', str(refresh.access_token), max_age=3600, httponly=False)
        return response
    except Exception:
        return redirect(next_url)


def google_one_tap_login_view(request):
    """
    Handle Google One Tap / Google Identity Services AJAX credential login.
    Verifies ID token with Google's tokeninfo API, then provisions or authenticates user.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    config = get_google_config(request)
    if not config['enabled'] or not config['client_id']:
        return JsonResponse({'success': False, 'message': 'Google sign-in is not enabled'}, status=400)

    credential = request.POST.get('credential') or ''
    if not credential and request.body:
        try:
            body_data = json.loads(request.body.decode('utf-8'))
            credential = body_data.get('credential', '')
        except Exception:
            pass

    if not credential:
        return JsonResponse({'success': False, 'message': 'Missing Google credential'}, status=400)

    # Verify ID token with Google's public tokeninfo endpoint
    try:
        verify_resp = requests.get(
            f"{GOOGLE_TOKENINFO_URL}?id_token={credential}",
            timeout=8,
        )
        token_info = verify_resp.json()
    except Exception as exc:
        logger.exception("Google tokeninfo error: %s", exc)
        return JsonResponse({'success': False, 'message': f'Google verification connection failed: {exc}'}, status=500)

    if 'error' in token_info:
        return JsonResponse({'success': False, 'message': token_info.get('error_description', 'Invalid token')}, status=400)

    # Verify client ID matches
    aud = token_info.get('aud')
    if aud != config['client_id']:
        logger.warning("Audience mismatch: %s != %s", aud, config['client_id'])
        return JsonResponse({'success': False, 'message': 'Google Client ID mismatch'}, status=400)

    email = (token_info.get('email') or '').strip().lower()
    if not email:
        return JsonResponse({'success': False, 'message': 'No email returned by Google'}, status=400)

    given_name = (token_info.get('given_name') or token_info.get('name') or email.split('@')[0]).strip()
    family_name = (token_info.get('family_name') or '').strip()

    user = User.objects.filter(email__iexact=email).first()
    is_new = False
    if not user:
        is_new = True
        user = User.objects.create_user(
            email=email,
            first_name=given_name,
            last_name=family_name or 'Client',
            role=User.Role.CLIENT,
            is_active=True,
            password=secrets.token_urlsafe(32),
        )
        ClientProfile.objects.create(
            user=user,
            is_email_verified=True,
            country='BD',
            currency=request.session.get('currency', 'BDT'),
        )
        logger.info("New client account created via Google One Tap: %s", email)
    else:
        if not user.is_active:
            return JsonResponse({'success': False, 'message': 'Account is inactive'}, status=403)
        if hasattr(user, 'profile') and not user.profile.is_email_verified:
            user.profile.is_email_verified = True
            user.profile.save(update_fields=['is_email_verified'])

    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    next_url = request.POST.get('next') or request.GET.get('next') or '/dashboard/'
    return JsonResponse({
        'success': True,
        'redirect': next_url,
        'is_new': is_new,
        'email': user.email,
        'name': user.get_full_name(),
    })

