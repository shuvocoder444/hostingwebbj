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
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from core.views import (
    landing_page_view,
    login_view,
    register_view,
    logout_view,
    dashboard_view,
    order_hosting_view,
    pay_invoice_view,
)
from core.admin_views import (
    admin_dashboard_view,
    admin_test_server_view,
    admin_whm_packages_api,
    admin_check_registrar_balance_view,
    admin_action_handler_view,
)

urlpatterns = [
    # ── Client Web UI Pages ───────────────────────────────────────────────────
    path('', landing_page_view, name='landing'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('hosting/order/', order_hosting_view, name='order_hosting'),
    path('billing/invoices/<uuid:invoice_id>/pay/', pay_invoice_view, name='pay_invoice'),

    # ── Custom Admin Management Portal ────────────────────────────────────────
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/servers/<uuid:server_id>/test/', admin_test_server_view, name='admin_test_server'),
    path('admin-dashboard/test-server/<uuid:server_id>/', admin_test_server_view),
    path('admin-dashboard/servers/<uuid:server_id>/whm-packages/', admin_whm_packages_api, name='admin_whm_packages'),
    path('admin-dashboard/registrars/<uuid:registrar_id>/balance/', admin_check_registrar_balance_view, name='admin_check_registrar_balance'),
    path('admin-dashboard/check-registrar-balance/<uuid:registrar_id>/', admin_check_registrar_balance_view),
    path('admin-dashboard/action/<str:action_type>/', admin_action_handler_view, name='admin_action_handler'),

    # ── Django Native Admin ───────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── OpenAPI Schema & Swagger Docs ─────────────────────────────────────────
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # ── API v1 Endpoints ──────────────────────────────────────────────────────
    path('api/v1/auth/', include('accounts.urls', namespace='accounts')),
    path('api/v1/billing/', include('billing.urls', namespace='billing')),
    path('api/v1/hosting/', include('hosting.urls', namespace='hosting')),
    path('api/v1/domains/', include('domains.urls', namespace='domains')),
]
