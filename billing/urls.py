from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BKashCallbackView,
    CryptomusIPNView,
    InvoiceViewSet,
    PaymentInitiateView,
    SSLCommerzIPNView,
    initiate_online_payment_view,
    payment_complete_return_view,
    payment_webhook_view,
)

app_name = 'billing'

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')

urlpatterns = [
    path('', include(router.urls)),
    path('pay/<uuid:invoice_id>/', PaymentInitiateView.as_view(), name='pay'),
    path('invoices/<uuid:invoice_id>/pay-online/', initiate_online_payment_view, name='invoice-pay-online'),
    path('ipn/sslcommerz/', SSLCommerzIPNView.as_view(), name='sslcommerz-ipn'),
    path('ipn/bkash/', BKashCallbackView.as_view(), name='bkash-callback'),
    path('ipn/cryptomus/', CryptomusIPNView.as_view(), name='cryptomus-ipn'),
    path('webhook/webkoders/', payment_webhook_view, name='webkoders-webhook'),
    path('complete/', payment_complete_return_view, name='webkoders-complete'),
]
