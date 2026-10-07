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
        default='VeloHoster — High Performance Cloud Web Hosting & Domains',
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
        default='Premium high-speed cloud web hosting, cPanel, BDIX, LiteSpeed, and domain registration with automated provisioning and instant Bangladeshi payment gateways (bKash, Nagad, SSLCommerz).',
        help_text='Meta description for Google SEO and social share previews (Facebook, WhatsApp, Twitter).'
    )
    meta_keywords = models.TextField(
        default='web hosting, bdix hosting, cpanel hosting, spaceship domain, bdwebs, buy domain bangladesh, bkash hosting, cheap hosting',
        blank=True,
        help_text='Comma-separated SEO keywords and tags.'
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

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site & SEO Setting'
        verbose_name_plural = 'Site & SEO Settings'

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
            setting = cls.objects.first()
            if not setting:
                setting = cls.objects.create(
                    company_name='VeloHoster',
                    site_title='VeloHoster — High Performance Cloud Web Hosting & Domains',
                    whatsapp_number='8801700000000',
                )
            cache.set(cache_key, setting, 300)
            return setting
        except Exception:
            # Fallback mock object if migrations not run yet
            class FallbackSetting:
                site_title = 'VeloHoster — High Performance Cloud Web Hosting & Domains'
                company_name = 'VeloHoster'
                tagline = 'Next-Gen NVMe Cloud & BDIX Hosting Platform'
                meta_description = 'Premium high-speed cloud web hosting, cPanel, BDIX, LiteSpeed, and domain registration with automated provisioning and instant Bangladeshi payment gateways.'
                meta_keywords = 'web hosting, bdix hosting, cpanel hosting, spaceship domain, bdwebs, buy domain bangladesh'
                logo_url = ''
                favicon_url = ''
                thumbnail_url = ''
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
            return FallbackSetting()

    def save(self, *args, **kwargs):
        from django.core.cache import cache
        super().save(*args, **kwargs)
        cache.delete('velohoster_site_settings_cache')
