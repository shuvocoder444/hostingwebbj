"""
Domains URL Routing
====================
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DomainSearchView,
    TLDPricingListView,
    DomainViewSet,
    OrderDomainAPIView,
    order_domain_web_view,
)

app_name = 'domains'

router = DefaultRouter()
router.register(r'my-domains', DomainViewSet, basename='domain')

urlpatterns = [
    # REST API endpoints (/api/v1/domains/...)
    path('search/', DomainSearchView.as_view(), name='search'),
    path('pricing/', TLDPricingListView.as_view(), name='pricing'),
    path('order/', OrderDomainAPIView.as_view(), name='api_order'),
    path('', include(router.urls)),

    # Web form endpoint
    path('web/order/', order_domain_web_view, name='web_order'),
]
