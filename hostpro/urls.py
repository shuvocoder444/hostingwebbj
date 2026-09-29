"""
HostPro Root URL Configuration
================================
All app-level URLs are namespaced and versioned under /api/v1/.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # OpenAPI schema endpoints
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # API v1 — each app registers its own router
    path('api/v1/auth/', include('accounts.urls', namespace='accounts')),
    path('api/v1/billing/', include('billing.urls', namespace='billing')),
    path('api/v1/hosting/', include('hosting.urls', namespace='hosting')),
    path('api/v1/domains/', include('domains.urls', namespace='domains')),
]
