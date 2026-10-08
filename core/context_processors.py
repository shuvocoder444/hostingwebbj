"""
Global Context Processors
==========================
Injects site-wide dynamic branding, SEO meta tags, social media links,
WhatsApp live chat, and logo configurations into every template context.
"""
from django.conf import settings
from .models import SiteSetting


def make_absolute_https_url(request, url):
    """Ensure URL is absolute and uses https protocol for Open Graph preview crawlers."""
    if not url:
        return ''
    url = str(url).strip()
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('http://'):
        return 'https://' + url[7:]
    if url.startswith('https://'):
        return url
    
    # Relative path (e.g. /static/img/og_thumbnail.png)
    host = 'velohoster.com'
    if hasattr(request, 'get_host'):
        h = request.get_host()
        if h and '127.0.0.1' not in h and 'localhost' not in h:
            host = h
    
    if not url.startswith('/'):
        url = '/' + url
    return f"https://{host}{url}"


def global_brand_context(request):
    """
    Load dynamic SiteSetting singleton and inject branding variables.
    """
    site = SiteSetting.get_settings()

    raw_num = getattr(site, 'whatsapp_number', '') or getattr(settings, 'WHATSAPP_SUPPORT_NUMBER', '8801700000000')
    clean_wa = ''.join(c for c in str(raw_num) if c.isdigit())
    if not clean_wa.startswith('880') and len(clean_wa) == 11 and clean_wa.startswith('01'):
        clean_wa = '88' + clean_wa

    company_name = getattr(site, 'company_name', '') or getattr(settings, 'COMPANY_NAME', 'VeloHoster')
    site_title = getattr(site, 'site_title', '') or f"{company_name} — High Performance Cloud Web Hosting & Domains"
    meta_desc = getattr(site, 'meta_description', '') or 'Premium high-speed cloud web hosting, cPanel, BDIX, LiteSpeed, and domain registration.'
    meta_keys = getattr(site, 'meta_keywords', '') or 'web hosting, bdix hosting, cpanel hosting, buy domain bangladesh'
    tagline = getattr(site, 'tagline', '') or 'Next-Gen Cloud Web Hosting'

    logo_url = getattr(site, 'logo_url', '') or '/static/img/logo.png'
    favicon_url = getattr(site, 'favicon_url', '') or '/static/img/favicon.png'
    thumbnail_url = getattr(site, 'thumbnail_url', '')

    # Absolute HTTPS URLs for Social Media Open Graph previews (WhatsApp, Facebook, Twitter, Telegram, LinkedIn)
    if thumbnail_url:
        og_image_url = make_absolute_https_url(request, thumbnail_url)
    elif logo_url:
        og_image_url = make_absolute_https_url(request, logo_url)
    else:
        og_image_url = make_absolute_https_url(request, '/static/img/og_thumbnail.png')

    # Absolute current page URL
    current_path = request.path if hasattr(request, 'path') else '/'
    host = 'velohoster.com'
    if hasattr(request, 'get_host'):
        h = request.get_host()
        if h and '127.0.0.1' not in h and 'localhost' not in h:
            host = h
    og_page_url = f"https://{host}{current_path}"

    return {
        'site_settings': site,
        'SITE_SETTINGS': site,
        'SHOW_HERO_SECTION': getattr(site, 'show_hero_section', True),
        'SITE_TITLE': site_title,
        'COMPANY_NAME': company_name,
        'SITE_TAGLINE': tagline,
        'META_DESCRIPTION': meta_desc,
        'META_KEYWORDS': meta_keys,
        'LOGO_URL': logo_url,
        'FAVICON_URL': favicon_url,
        'THUMBNAIL_URL': thumbnail_url or '/static/img/og_thumbnail.png',
        'OG_IMAGE_URL': og_image_url,
        'OG_PAGE_URL': og_page_url,
        'WHATSAPP_NUMBER': clean_wa or '8801700000000',
        'WHATSAPP_DISPLAY_NUMBER': getattr(site, 'support_phone', '') or getattr(settings, 'WHATSAPP_DISPLAY_NUMBER', '+880 1700-000000'),
        'SUPPORT_EMAIL': getattr(site, 'support_email', 'support@velohoster.com'),
        'SUPPORT_PHONE': getattr(site, 'support_phone', '+880 1700-000000'),
        'OFFICE_ADDRESS': getattr(site, 'office_address', 'Dhaka, Bangladesh'),
        'FACEBOOK_URL': getattr(site, 'facebook_url', ''),
        'YOUTUBE_URL': getattr(site, 'youtube_url', ''),
        'LINKEDIN_URL': getattr(site, 'linkedin_url', ''),
        'INSTAGRAM_URL': getattr(site, 'instagram_url', ''),
        'TWITTER_URL': getattr(site, 'twitter_url', ''),
        'TELEGRAM_URL': getattr(site, 'telegram_url', ''),
    }
