"""
HostPro Root URL Configuration
================================
Routes:
  - Web UI: Landing page, Login, Register, Logout, Dashboard, Order, Payment
  - API v1: Namespaced REST endpoints (/api/v1/...)
  - OpenAPI & Swagger: Interactive documentation
  - Django Admin: Staff management
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

urlpatterns = [
    # ── Web UI Pages ──────────────────────────────────────────────────────────
    path('', landing_page_view, name='landing'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('hosting/order/', order_hosting_view, name='order_hosting'),
    path('billing/invoices/<uuid:invoice_id>/pay/', pay_invoice_view, name='pay_invoice'),

    # ── Django Admin ──────────────────────────────────────────────────────────
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
