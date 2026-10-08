"""
SEO Sitemaps Configuration for VeloHoster
==========================================
Generates dynamic sitemap.xml for all public marketing, hosting, domain, and company pages.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap for all main public pages."""
    priority = 0.9
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return [
            'landing',
            'hosting_bdix',
            'hosting_singapore',
            'hosting_usa',
            'hosting_turbo_cloud',
            'hosting_premium',
            'hosting_reseller',
            'hosting_vps',
            'domain_register',
            'domain_transfer',
            'cart_domain',
            'about_us',
            'our_datacenter',
            'contact_us',
            'blog',
            'login',
            'register',
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        if item == 'landing':
            return 1.0
        elif 'hosting' in item or 'domain' in item:
            return 0.9
        elif item in ('contact_us', 'about_us', 'our_datacenter', 'blog'):
            return 0.8
        return 0.5

    def changefreq(self, item):
        if item == 'landing':
            return 'daily'
        elif 'hosting' in item or 'domain' in item:
            return 'weekly'
        return 'monthly'

