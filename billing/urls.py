from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet, PaymentInitiateView, SSLCommerzIPNView, BKashCallbackView, CryptomusIPNView

app_name = 'billing'

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')

urlpatterns = [
    path('', include(router.urls)),
    path('pay/<uuid:invoice_id>/', PaymentInitiateView.as_view(), name='pay'),
    path('ipn/sslcommerz/', SSLCommerzIPNView.as_view(), name='sslcommerz-ipn'),
    path('ipn/bkash/', BKashCallbackView.as_view(), name='bkash-callback'),
    path('ipn/cryptomus/', CryptomusIPNView.as_view(), name='cryptomus-ipn'),
]
