"""
HostPro Root URL Configuration
================================
Routes:
  - Web UI: Landing page, Login, Register, Logout, Client Dashboard, Order, Payment
  - Custom Admin Portal: Full administrative operations (/admin-dashboard/)
  - API v1: Namespaced REST endpoints (/api/v1/...)
  - OpenAPI & Swagger: Interactive documentation
  - Django Admin: Staff fallback management (/admin/)
"""
from functools import wraps
from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import IsAdminUser

from core.admin_views import (
    admin_action_handler_view,
    admin_check_registrar_balance_view,
    admin_client_details_api,
    admin_dashboard_view,
    admin_login_as_client_view,
    admin_test_server_view,
    admin_whm_packages_api,
    is_staff_or_admin,
)


def admin_only_view(view_func):
    """Decorator to restrict Swagger / OpenAPI documentation strictly to logged-in admins."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        if not is_staff_or_admin(request.user):
            messages.error(request, "Access restricted. Staff or Administrator privileges required.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
from core.cart_views import (
    ajax_domain_check_view,
    ajax_domain_bulk_search_view,
    ajax_domain_ai_generate_view,
    cart_checkout_view,
    cart_complete_order_view,
    cart_configure_view,
    cart_domain_view,
)
from core.page_views import (
    about_us_view,
    blog_view,
    contact_us_view,
    domain_register_view,
    domain_transfer_view,
    hosting_bdix_view,
    hosting_premium_view,
    hosting_reseller_view,
    hosting_singapore_view,
    hosting_turbo_cloud_view,
    hosting_usa_view,
    hosting_vps_view,
    our_datacenter_view,
)
from core.views import (
    dashboard_view,
    landing_page_view,
    login_view,
    logout_view,
    order_hosting_view,
    pay_invoice_view,
    register_view,
    service_change_password_view,
    service_detail_view,
    service_request_cancellation_view,
    service_sso_view,
)

from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from core.sitemaps import StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
}

def robots_txt_view(request):
    """Dynamic robots.txt generator for search engine crawlers."""
    host = request.get_host() or 'velohoster.com'
    content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /admin-dashboard/
Disallow: /billing/
Disallow: /dashboard/
Disallow: /services/
Disallow: /api/

Sitemap: https://{host}/sitemap.xml
"""
    return HttpResponse(content, content_type='text/plain')

urlpatterns = [
    # ── Search Engine Optimization (SEO) Sitemaps & Robots ────────────────────
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt_view, name='robots_txt'),

    # ── Client Web UI Pages ───────────────────────────────────────────────────
    path('', landing_page_view, name='landing'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('hosting/order/', order_hosting_view, name='order_hosting'),
    path('billing/invoices/<uuid:invoice_id>/pay/', pay_invoice_view, name='pay_invoice'),

    # ── Dedicated Product & Marketing Pages ───────────────────────────────────
    path('about-us/', about_us_view, name='about_us'),
    path('contact-us/', contact_us_view, name='contact_us'),
    path('our-datacenter/', our_datacenter_view, name='our_datacenter'),
    path('blog/', blog_view, name='blog'),
    
    # Domains
    path('domain/register/', domain_register_view, name='domain_register'),
    path('register-domain/', domain_register_view),
    path('domain/transfer/', domain_transfer_view, name='domain_transfer'),
    path('transfer-domain/', domain_transfer_view),

    # Hosting Locations & Product Specializations
    path('hosting/singapore-nvme/', hosting_singapore_view, name='hosting_singapore'),
    path('hosting/singapore/', hosting_singapore_view),
    path('hosting/usa-nvme/', hosting_usa_view, name='hosting_usa'),
    path('hosting/usa/', hosting_usa_view),
    path('hosting/bdix/', hosting_bdix_view, name='hosting_bdix'),
    path('hosting/bdix-server/', hosting_bdix_view),
    path('hosting/premium/', hosting_premium_view, name='hosting_premium'),
    path('hosting/turbo-cloud/', hosting_turbo_cloud_view, name='hosting_turbo_cloud'),
    path('hosting/ecommerce/', hosting_turbo_cloud_view),
    path('hosting/reseller/', hosting_reseller_view, name='hosting_reseller'),
    path('hosting/vps/', hosting_vps_view, name='hosting_vps'),

    # ── Service Details & cPanel Management ───────────────────────────────────
    path('services/<uuid:account_id>/', service_detail_view, name='service_detail'),
    path('services/<uuid:account_id>/sso/', service_sso_view, name='service_sso'),
    path('services/<uuid:account_id>/sso/<str:shortcut>/', service_sso_view, name='service_sso_shortcut'),
    path('services/<uuid:account_id>/change-password/', service_change_password_view, name='service_change_password'),
    path('services/<uuid:account_id>/request-cancellation/', service_request_cancellation_view, name='service_request_cancellation'),

    # ── Shopping Cart & Multi-Step Ordering Funnel ────────────────────────────
    path('cart/', cart_domain_view, name='cart_domain'),
    path('cart/configure/', cart_configure_view, name='cart_configure'),
    path('cart/checkout/', cart_checkout_view, name='cart_checkout'),
    path('cart/complete/', cart_complete_order_view, name='cart_complete_order'),
    path('api/v1/domains/ajax-check/', ajax_domain_check_view, name='ajax_domain_check'),
    path('cart/ajax/domain-check/', ajax_domain_check_view, name='cart_ajax_domain_check'),
    path('api/v1/domains/bulk-search/', ajax_domain_bulk_search_view, name='ajax_domain_bulk_search'),
    path('api/v1/domains/ai-generate/', ajax_domain_ai_generate_view, name='ajax_domain_ai_generate'),

    # ── Custom Admin Management Portal ────────────────────────────────────────
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/servers/<uuid:server_id>/test/', admin_test_server_view, name='admin_test_server'),
    path('admin-dashboard/test-server/<uuid:server_id>/', admin_test_server_view),
    path('admin-dashboard/servers/<uuid:server_id>/whm-packages/', admin_whm_packages_api, name='admin_whm_packages'),
    path('admin-dashboard/registrars/<uuid:registrar_id>/balance/', admin_check_registrar_balance_view, name='admin_check_registrar_balance'),
    path('admin-dashboard/check-registrar-balance/<uuid:registrar_id>/', admin_check_registrar_balance_view),
    path('admin-dashboard/clients/<uuid:client_id>/details/', admin_client_details_api, name='admin_client_details'),
    path('admin-dashboard/clients/<uuid:client_id>/login-as/', admin_login_as_client_view, name='admin_login_as_client'),
    path('admin-dashboard/action/<str:action_type>/', admin_action_handler_view, name='admin_action_handler'),

    # ── Django Native Admin ───────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── OpenAPI Schema & Swagger Docs (Admin Restricted Only) ─────────────────
    path('api/schema/', admin_only_view(SpectacularAPIView.as_view(permission_classes=[IsAdminUser])), name='schema'),
    path('api/docs/', admin_only_view(SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[IsAdminUser])), name='swagger-ui'),
    path('api/redoc/', admin_only_view(SpectacularRedocView.as_view(url_name='schema', permission_classes=[IsAdminUser])), name='redoc'),

    # ── API v1 Endpoints ──────────────────────────────────────────────────────
    path('api/v1/auth/', include('accounts.urls', namespace='accounts')),
    path('api/v1/billing/', include('billing.urls', namespace='billing')),
    path('api/v1/hosting/', include('hosting.urls', namespace='hosting')),
    path('api/v1/domains/', include('domains.urls', namespace='domains')),
]
