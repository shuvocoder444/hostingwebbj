"""
Core Models — Site Branding, SEO, Social Media & System Settings
=================================================================
Provides persistent singleton configuration for:
  - Website Title, Meta Description, Keywords/Tags
  - Social Share Preview Thumbnail (og:image / WhatsApp preview)
  - Logo and Favicon URLs / Assets
  - WhatsApp Live Support Number
  - Social Media Links (Facebook, YouTube, LinkedIn, Instagram, Twitter, Telegram)
"""
import uuid

from django.db import models


class SiteSetting(models.Model):
    """
    Singleton model for Site Identity, SEO, Social Media, WhatsApp, and Branding.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Site Identity & SEO ──
    site_title = models.CharField(
        max_length=200,
        default='VeloHoster: NVMe Web Hosting and Domains in Bangladesh',
        help_text='Main website title shown in search engines and social share previews.'
    )
    company_name = models.CharField(
        max_length=100,
        default='VeloHoster',
        help_text='Brand name used across navigation, invoice header, and copyright.'
    )
    tagline = models.CharField(
        max_length=255,
        default='Next-Gen NVMe Cloud & BDIX Hosting Platform',
        blank=True
    )
    meta_description = models.TextField(
        default='NVMe web hosting and domain registration with cPanel, reliable support, and server locations in Bangladesh, Singapore, the USA, and Europe.',
        help_text='Meta description for Google SEO and social share previews (Facebook, WhatsApp, Twitter).'
    )
    meta_keywords = models.TextField(
        default='',
        blank=True,
        help_text='Comma-separated SEO keywords and tags.'
    )

    # ── Homepage Layout Controls ──
    show_hero_section = models.BooleanField(
        default=True,
        help_text='Toggle Hero Section on the Homepage.'
    )

    # ── Media & Branding Assets ──
    logo_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Custom Logo Image URL (e.g. /static/img/logo.png or https://...)'
    )
    favicon_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Browser Tab Favicon URL'
    )
    thumbnail_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Social Share Banner / OG Thumbnail Image URL (1200x630 for WhatsApp / Facebook previews).'
    )

    # ── Support & Contact ──
    whatsapp_number = models.CharField(
        max_length=50,
        default='8801700000000',
        help_text='WhatsApp Support phone number (e.g. +8801712345678 or 01712345678)'
    )
    support_email = models.EmailField(
        max_length=100,
        default='support@velohoster.com',
        blank=True
    )
    support_phone = models.CharField(
        max_length=50,
        default='+880 1700-000000',
        blank=True
    )
    office_address = models.CharField(
        max_length=255,
        default='Dhaka, Bangladesh',
        blank=True
    )

    # ── Social Media Links ──
    facebook_url = models.URLField(max_length=255, blank=True, default='')
    youtube_url = models.URLField(max_length=255, blank=True, default='')
    linkedin_url = models.URLField(max_length=255, blank=True, default='')
    instagram_url = models.URLField(max_length=255, blank=True, default='')
    twitter_url = models.URLField(max_length=255, blank=True, default='')
    telegram_url = models.URLField(max_length=255, blank=True, default='')

    # ── WebKoders Payment Gateway Settings ──
    webkoders_base_url = models.CharField(
        max_length=255,
        default='https://payment.webkoders.com',
        blank=True,
        help_text='WebKoders Gateway Base URL'
    )
    webkoders_api_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='WebKoders API Key (Merchant API Key)'
    )
    webkoders_api_secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='WebKoders API Secret Key (Used for HMAC-SHA256 signature verification)'
    )
    webkoders_webhook_url = models.CharField(
        max_length=255,
        blank=True,
        default='https://velohoster.com/payments/webhook/',
        help_text='WebKoders Webhook / Callback URL for payment IPN notifications'
    )

    # ── Bangla QR Payment Gateway Settings ──
    enable_bangla_qr = models.BooleanField(
        default=True,
        help_text='Enable Bangla QR (বাংলা কিউআর) on checkout and invoice payment pages.'
    )
    bangla_qr_image_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Bangla QR Image URL or static path (e.g. /static/img/bangla_qr.png)'
    )
    bangla_qr_merchant_name = models.CharField(
        max_length=150,
        blank=True,
        default='VeloHoster / Bangla QR',
        help_text='Merchant Name displayed with Bangla QR'
    )
    bangla_qr_merchant_number = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Merchant Contact / Mobile Banking Number'
    )
    bangla_qr_instructions = models.TextField(
        blank=True,
        default='যেকোনো ব্যাংক অ্যাপ (City Bank, BRAC, EBL, ইত্যাদি) অথবা বিকাশ, নগদ, উপায় অ্যাপের "QR স্ক্যান" অপশন দিয়ে উপরের বাংলা কিউআর (Bangla QR) কোডটি স্ক্যান করে পেমেন্ট সম্পন্ন করুন এবং নিচে TrxID ও আপনার মোবাইল নম্বর প্রদান করুন।',
        help_text='Payment instructions shown to the customer on checkout.'
    )

    # ── International & Crypto Payment Gateway Settings ──
    cryptomus_merchant_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Cryptomus Merchant UUID from Cryptomus Dashboard'
    )
    cryptomus_payment_api_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Cryptomus Payment API Key'
    )
    usdt_trc20_wallet = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='USDT TRC-20 Wallet Address (Binance / Trust Wallet)'
    )
    usdt_bep20_wallet = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='USDT BEP-20 (BNB Smart Chain) Wallet Address'
    )
    binance_pay_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Binance Pay ID / Binance Email / Pay QR'
    )

    # ── Google OAuth & Social Login Settings ──
    enable_google_login = models.BooleanField(
        default=True,
        help_text='Enable Google/Gmail 1-Click Login and Registration for customers.'
    )
    google_client_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Google OAuth 2.0 Web Client ID (from Google Cloud Console)'
    )
    google_client_secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Google OAuth 2.0 Client Secret'
    )

    # ── Currency & Exchange Rate ──
    bdt_per_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=127.00,
        help_text='Conversion Rate: How many BDT per 1 USD (e.g. 127.00)'
    )

    # ── Email & SMTP Settings ──
    require_email_otp = models.BooleanField(
        default=True,
        help_text='Require 6-digit Email OTP verification when registering new accounts.'
    )
    smtp_host = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Custom SMTP Server Host (e.g. smtp.gmail.com or leave blank to use server mail).'
    )
    smtp_port = models.IntegerField(
        default=587,
        help_text='SMTP Port (587 for TLS, 465 for SSL).'
    )
    smtp_user = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='SMTP Username / Email (e.g. noreply@velohoster.com).'
    )
    smtp_password = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='SMTP Password.'
    )
    smtp_use_tls = models.BooleanField(
        default=True,
        help_text='Use STARTTLS (Port 587).'
    )
    smtp_use_ssl = models.BooleanField(
        default=False,
        help_text='Use SSL (Port 465).'
    )
    smtp_from_email = models.CharField(
        max_length=255,
        blank=True,
        default='VeloHoster <noreply@velohoster.com>',
        help_text='Sender Email Address displayed in inbox.'
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site & SEO Setting'
        verbose_name_plural = 'Site & SEO Settings'

    def get_google_client_id(self):
        from django.conf import settings
        return (self.google_client_id or getattr(settings, 'GOOGLE_CLIENT_ID', '')).strip()

    def get_google_client_secret(self):
        from django.conf import settings
        return (self.google_client_secret or getattr(settings, 'GOOGLE_CLIENT_SECRET', '')).strip()

    def __str__(self):
        return f"{self.company_name} Settings ({self.site_title})"

    @classmethod
    def get_settings(cls):
        """Get or create singleton instance with cache support."""
        from django.core.cache import cache
        cache_key = 'velohoster_site_settings_cache'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            # Prefer row with logo_url configured, or most recently updated row
            setting = cls.objects.exclude(logo_url='').order_by('-updated_at').first() or cls.objects.order_by('-updated_at').first()
            if not setting:
                setting = cls.objects.create(
                    company_name='VeloHoster',
                    site_title='VeloHoster: NVMe Web Hosting and Domains in Bangladesh',
                    logo_url='/static/img/logo.png',
                    favicon_url='/static/img/favicon.png',
                    whatsapp_number='8801700000000',
                )
            cache.set(cache_key, setting, 300)
            return setting
        except Exception:
            # Fallback mock object if migrations not run yet
            class FallbackSetting:
                site_title = 'VeloHoster: NVMe Web Hosting and Domains in Bangladesh'
                company_name = 'VeloHoster'
                tagline = 'Next-Gen NVMe Cloud & BDIX Hosting Platform'
                meta_description = 'NVMe web hosting and domain registration with cPanel, reliable support, and server locations in Bangladesh, Singapore, the USA, and Europe.'
                meta_keywords = ''
                show_hero_section = True
                logo_url = '/static/img/logo.png'
                favicon_url = '/static/img/favicon.png'
                thumbnail_url = '/static/img/og_thumbnail.png'
                whatsapp_number = '8801700000000'
                support_email = 'support@velohoster.com'
                support_phone = '+880 1700-000000'
                office_address = 'Dhaka, Bangladesh'
                facebook_url = ''
                youtube_url = ''
                linkedin_url = ''
                instagram_url = ''
                twitter_url = ''
                telegram_url = ''
                webkoders_base_url = 'https://payment.webkoders.com'
                webkoders_api_key = ''
                webkoders_api_secret = ''
                webkoders_webhook_url = 'https://velohoster.com/payments/webhook/'
                bdt_per_usd = 127.00
                enable_google_login = True
                google_client_id = ''
                google_client_secret = ''
                def get_google_client_id(self):
                    return ''
                def get_google_client_secret(self):
                    return ''
            return FallbackSetting()

    def save(self, *args, **kwargs):
        from django.core.cache import cache
        super().save(*args, **kwargs)
        cache.delete('velohoster_site_settings_cache')
