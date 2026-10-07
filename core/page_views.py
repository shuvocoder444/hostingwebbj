"""
Marketing & Product Specific Dedicated Page Views
===================================================
Handles dedicated landing pages for:
- Company: About Us, Contact Us, Our Datacenter, Blog
- Domains: Register Domain, Transfer Domain
- Hosting: Singapore NVMe, USA Super-Fast, BDIX Server, Premium Business, Turbo Cloud, Reseller, VPS
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from hosting.models import HostingPackage
from domains.models import TLDPricing
from core.models import SiteSetting


def about_us_view(request):
    """About Us & Company Overview Page."""
    return render(request, 'pages/about_us.html', {
        'page_title': 'About Us — Next-Gen Cloud Infrastructure',
    })


def contact_us_view(request):
    """Contact Us & Technical Support Desk Page."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_text = request.POST.get('message', '').strip()
        
        if name and email and message_text:
            messages.success(request, f"Thank you {name}! Your message has been received. Our technical team will reply to {email} shortly.")
        else:
            messages.error(request, "Please fill in all required fields.")
            
    return render(request, 'pages/contact_us.html', {
        'page_title': 'Contact Us — 24/7 Priority Support Desk',
    })


def our_datacenter_view(request):
    """Datacenter Locations, Network Specs, and Speed Test Pings Page."""
    return render(request, 'pages/our_datacenter.html', {
        'page_title': 'Our Global Datacenters & Tier-4 Network Infrastructure',
    })


def blog_view(request):
    """Hosting Knowledge Base, Tutorials & Tech Articles."""
    return render(request, 'pages/blog.html', {
        'page_title': 'VeloHoster Blog — Web Hosting, Cloud & WordPress Insights',
    })


def domain_register_view(request):
    """Dedicated Domain Registration & Search Portal."""
    tld_prices = TLDPricing.objects.filter(is_active=True).select_related('registrar').order_by('register_price')
    return render(request, 'pages/domain_register.html', {
        'page_title': 'Register a Domain Name — Cheap & Instant Registration',
        'tld_prices': tld_prices,
    })


def domain_transfer_view(request):
    """Domain Transfer to VeloHoster with 1 Year Free Extension."""
    tld_prices = TLDPricing.objects.filter(is_active=True).select_related('registrar').order_by('transfer_price')
    return render(request, 'pages/domain_transfer.html', {
        'page_title': 'Transfer Your Domain — Zero Downtime & 1-Year Free Renewal',
        'tld_prices': tld_prices,
    })


def hosting_singapore_view(request):
    """Singapore NVMe SSD High Performance Web Hosting."""
    packages = HostingPackage.objects.filter(is_active=True).order_by('monthly_price')
    return render(request, 'pages/hosting_singapore.html', {
        'page_title': 'Singapore NVMe SSD Web Hosting — Ultra Low Latency',
        'packages': packages,
        'location': 'Singapore 🇸🇬',
    })


def hosting_usa_view(request):
    """USA NVMe SSD Super Fast Web Hosting."""
    packages = HostingPackage.objects.filter(is_active=True).order_by('monthly_price')
    return render(request, 'pages/hosting_usa.html', {
        'page_title': 'USA NVMe SSD Web Hosting — Super Fast Global CDN',
        'packages': packages,
        'location': 'USA 🇺🇸',
    })


def hosting_bdix_view(request):
    """Premium BDIX 10Gbps Bangladeshi Server Hosting."""
    packages = HostingPackage.objects.filter(is_active=True).order_by('monthly_price')
    return render(request, 'pages/hosting_bdix.html', {
        'page_title': 'Premium BDIX Server Hosting — 1-5ms Ping Across Bangladesh',
        'packages': packages,
        'location': 'Dhaka BDIX 🇧🇩',
    })


def hosting_premium_view(request):
    """Premium Hosting for Business & High-Traffic Corporate Websites."""
    packages = HostingPackage.objects.filter(is_active=True).order_by('monthly_price')
    return render(request, 'pages/hosting_premium.html', {
        'page_title': 'Premium Business Web Hosting — Dedicated Performance & VIP Support',
        'packages': packages,
    })


def hosting_turbo_cloud_view(request):
    """Turbo Cloud Hosting Optimized for WooCommerce & E-Commerce."""
    packages = HostingPackage.objects.filter(is_active=True).order_by('monthly_price')
    return render(request, 'pages/hosting_turbo_cloud.html', {
        'page_title': 'Turbo Cloud E-Commerce Hosting — LiteSpeed & Redis Cache',
        'packages': packages,
    })


def hosting_reseller_view(request):
    """Cheap & Powerful White-Label cPanel/WHM Reseller Hosting."""
    return render(request, 'pages/hosting_reseller.html', {
        'page_title': 'Cheap Reseller Web Hosting — 100% White Label with WHM',
    })


def hosting_vps_view(request):
    """Managed Cloud KVM VPS Hosting."""
    return render(request, 'pages/hosting_vps.html', {
        'page_title': 'Managed Cloud VPS Hosting — Dedicated KVM NVMe Performance',
    })
