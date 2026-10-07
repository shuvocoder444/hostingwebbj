"""
Global Context Processors
==========================
Injects site-wide dynamic branding, SEO meta tags, social media links,
WhatsApp live chat, and logo configurations into every template context.
"""
from django.conf import settings
from .models import SiteSetting


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
    meta_desc = getattr(site, 'meta_description', '')
    meta_keys = getattr(site, 'meta_keywords', '')
    tagline = getattr(site, 'tagline', '')

    logo_url = getattr(site, 'logo_url', '')
    favicon_url = getattr(site, 'favicon_url', '')
    thumbnail_url = getattr(site, 'thumbnail_url', '')

    # Build absolute URLs for Open Graph if relative paths provided
    if thumbnail_url:
        if not thumbnail_url.startswith('http'):
            thumbnail_url = request.build_absolute_uri(thumbnail_url)
    elif logo_url:
        if not logo_url.startswith('http'):
            thumbnail_url = request.build_absolute_uri(logo_url)
        else:
            thumbnail_url = logo_url
    else:
        # Default site fallback image
        thumbnail_url = request.build_absolute_uri('/static/img/logo.png')

    return {
        'site_settings': site,
        'SITE_SETTINGS': site,
        'SITE_TITLE': site_title,
        'COMPANY_NAME': company_name,
        'SITE_TAGLINE': tagline,
        'META_DESCRIPTION': meta_desc,
        'META_KEYWORDS': meta_keys,
        'LOGO_URL': logo_url,
        'FAVICON_URL': favicon_url,
        'THUMBNAIL_URL': thumbnail_url,
        'OG_IMAGE_URL': thumbnail_url,
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
