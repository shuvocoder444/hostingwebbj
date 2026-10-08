"""
Core Multi-Currency & GeoIP Detection Engine
============================================
Provides automatic geolocation detection (BDT for Bangladesh visitors, USD for international),
session/cookie persistence, manual currency switching, and real-time price conversion.
"""
import logging
import urllib.request
import json
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_EXCHANGE_RATE = Decimal('120.00')  # 1 USD = 120 BDT


def get_client_ip(request) -> str:
    """Extract real client IP address from proxy / Cloudflare headers."""
    if not request:
        return '127.0.0.1'
    
    # 1. Cloudflare connecting IP
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip.strip()
    
    # 2. X-Real-IP
    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip.strip()
    
    # 3. X-Forwarded-For (first IP in chain)
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        parts = [p.strip() for p in xff.split(',') if p.strip()]
        if parts:
            return parts[0]
    
    # 4. Fallback remote address
    return request.META.get('REMOTE_ADDR', '127.0.0.1').strip()


def is_private_ip(ip: str) -> bool:
    """Check if IP address is localhost or private LAN range."""
    if not ip or ip in ('127.0.0.1', 'localhost', '::1', 'testserver'):
        return True
    if ip.startswith(('10.', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.', '172.20.',
                      '172.21.', '172.22.', '172.23.', '172.24.', '172.25.', '172.26.',
                      '172.27.', '172.28.', '172.29.', '172.30.', '172.31.')):
        return True
    return False


def get_client_country(request) -> str:
    """
    Detect visitor's country ISO code (e.g. 'BD', 'US', 'GB', 'IN').
    Uses Cloudflare header when present, or cached GeoIP lookup.
    """
    if not request:
        return 'BD'
    
    # 1. Cloudflare direct IP Country header (zero latency)
    cf_country = request.META.get('HTTP_CF_IPCOUNTRY')
    if cf_country and len(cf_country.strip()) == 2:
        return cf_country.strip().upper()
    
    # 2. Check client IP
    ip = get_client_ip(request)
    if is_private_ip(ip):
        return 'BD'
    
    # 3. Cached GeoIP lookup
    cache_key = f"velohoster_geoip_{ip.replace(':', '_')}"
    cached_country = cache.get(cache_key)
    if cached_country:
        return cached_country
    
    # 4. Fast lightweight IP API lookup with short timeout
    detected_country = 'BD'
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,countryCode"
        req = urllib.request.Request(url, headers={'User-Agent': 'VeloHoster-GeoIP/1.0'})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == 'success' and data.get('countryCode'):
                detected_country = data['countryCode'].upper()
    except Exception as exc:
        logger.debug("GeoIP lookup failed for IP %s: %s (fallback to BD)", ip, exc)
        detected_country = 'BD'
    
    # Cache result for 24 hours
    cache.set(cache_key, detected_country, 86400)
    return detected_country


def get_exchange_rate() -> Decimal:
    """Get BDT per 1 USD exchange rate from SiteSetting singleton or default."""
    try:
        from core.models import SiteSetting
        setting = SiteSetting.get_settings()
        rate = getattr(setting, 'bdt_per_usd', None)
        if rate and Decimal(str(rate)) > 0:
            return Decimal(str(rate))
    except Exception:
        pass
    return DEFAULT_EXCHANGE_RATE


def get_current_currency(request) -> str:
    """
    Determine active currency for current request:
      - If explicitly chosen in session/cookie or URL (?currency=USD), use that.
      - Otherwise, automatically detect visitor country:
          'BD' -> 'BDT'
          Outside 'BD' -> 'USD'
    """
    if not request:
        return 'BDT'
    
    # 1. Query parameter override (e.g. ?currency=USD or ?currency=BDT)
    q_curr = request.GET.get('currency', '').strip().upper()
    if q_curr in ('BDT', 'USD'):
        if hasattr(request, 'session'):
            request.session['currency'] = q_curr
        return q_curr
    
    # 2. Session value
    if hasattr(request, 'session') and request.session.get('currency'):
        curr = request.session.get('currency').strip().upper()
        if curr in ('BDT', 'USD'):
            return curr
    
    # 3. Cookie value
    cookie_curr = request.COOKIES.get('currency', '').strip().upper()
    if cookie_curr in ('BDT', 'USD'):
        if hasattr(request, 'session'):
            request.session['currency'] = cookie_curr
        return cookie_curr
    
    # 4. Auto-detect from Country Geolocation
    country = get_client_country(request)
    if country == 'BD':
        auto_curr = 'BDT'
    else:
        auto_curr = 'USD'
    
    if hasattr(request, 'session'):
        request.session['currency'] = auto_curr
    return auto_curr


def convert_bdt_to_usd(amount_bdt, rate=None) -> Decimal:
    """Convert BDT amount to USD with 2 decimal precision."""
    if amount_bdt is None or amount_bdt == '':
        return Decimal('0.00')
    try:
        bdt = Decimal(str(amount_bdt))
        if bdt == 0:
            return Decimal('0.00')
        r = rate or get_exchange_rate()
        return round(bdt / Decimal(str(r)), 2)
    except Exception:
        return Decimal('0.00')


def convert_price(amount_bdt, target_currency='BDT', rate=None) -> Decimal:
    """Return converted price in target currency."""
    if target_currency == 'USD':
        return convert_bdt_to_usd(amount_bdt, rate)
    try:
        return Decimal(str(amount_bdt)) if amount_bdt is not None else Decimal('0.00')
    except Exception:
        return Decimal('0.00')


def format_money(amount_bdt, currency='BDT', rate=None, show_symbol=True) -> str:
    """
    Format price nicely for display:
      - BDT: '৳250' or '৳2,400'
      - USD: '$2.10' or '$20.00'
    """
    if amount_bdt is None:
        return '৳0' if currency == 'BDT' else '$0.00'
    
    if currency == 'USD':
        usd_val = convert_bdt_to_usd(amount_bdt, rate)
        sym = '$' if show_symbol else ''
        return f"{sym}{usd_val:,.2f}"
    else:
        try:
            bdt_val = Decimal(str(amount_bdt))
            sym = '৳' if show_symbol else ''
            if bdt_val % 1 == 0:
                return f"{sym}{int(bdt_val):,}"
            return f"{sym}{bdt_val:,.2f}"
        except Exception:
            return f"৳{amount_bdt}"

