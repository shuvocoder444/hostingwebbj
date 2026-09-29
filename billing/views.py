"""
Billing Views — Invoices + IPN Webhooks
=========================================
Includes full IPN handling for SSLCommerz and bKash with signature verification.

IPN Security policy:
  1. ALWAYS verify the gateway signature BEFORE reading any data.
  2. Log the raw IPN payload for audit trail.
  3. Process the payment in an atomic transaction.
  4. Return 200 quickly — heavy work is delegated to Celery tasks.
"""
import logging
from decimal import Decimal

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema

from .models import Invoice
from .serializers import InvoiceSerializer, InvoiceDetailSerializer
from .services import PaymentService
from .gateway_factory import get_payment_gateway, BKashGateway
from core.cache import make_cache_key, TTL_INVOICE_LIST
from core.exceptions import InvalidIPNSignature, PaymentGatewayError

logger = logging.getLogger('billing')


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/billing/invoices/       — List client's invoices (cached)
    GET /api/v1/billing/invoices/{id}/  — Invoice detail with line items
    """
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['status', 'invoice_type']
    search_fields = ['invoice_number']
    ordering_fields = ['issued_date', 'due_date', 'total']

    def get_queryset(self):
        """
        User-scoped queryset.
        select_related + prefetch_related eliminates N+1 on related objects.
        """
        return (
            Invoice.objects
            .filter(user=self.request.user)
            .select_related('hosting_account', 'user')
            .prefetch_related('items', 'transactions')
            .order_by('-issued_date')
        )

    def get_serializer_class(self):
        return InvoiceDetailSerializer if self.action == 'retrieve' else InvoiceSerializer

    def list(self, request, *args, **kwargs):
        """Cache-Aside: return cached invoice list or load from DB."""
        cache_key = make_cache_key('invoice_list', str(request.user.id))
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("Invoice list cache HIT for user %s", request.user.id)
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=TTL_INVOICE_LIST)
        return response


class PaymentInitiateView(APIView):
    """
    POST /api/v1/billing/pay/{invoice_id}/
    Initiate payment via specified gateway.
    Body: {"gateway": "bkash"} or {"gateway": "sslcommerz"}
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary='Initiate payment for an invoice', tags=['Billing'])
    def post(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id, user=request.user)
        except Invoice.DoesNotExist:
            return Response({'detail': 'Invoice not found.'}, status=status.HTTP_404_NOT_FOUND)

        if invoice.status == Invoice.Status.PAID:
            return Response({'detail': 'Invoice already paid.'}, status=status.HTTP_409_CONFLICT)

        gateway_name = request.data.get('gateway', 'bkash')
        try:
            gateway = get_payment_gateway(gateway_name)
            result = gateway.initiate_payment(
                invoice=invoice,
                customer=request.user,
                callback_url=request.build_absolute_uri(
                    f'/api/v1/billing/ipn/{gateway_name}/'
                ),
            )
        except PaymentGatewayError as exc:
            logger.error("Payment initiation failed: %s", exc)
            return Response(
                {'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY
            )

        return Response(result, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class SSLCommerzIPNView(APIView):
    """
    POST /api/v1/billing/ipn/sslcommerz/
    Handles SSLCommerz IPN (Instant Payment Notification).

    Security: Verifies via SSLCommerz validation API before processing.
    This endpoint must be publicly accessible (no auth required).
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # No JWT — this is called by SSLCommerz server

    def post(self, request):
        data = request.data
        logger.info("SSLCommerz IPN received: tran_id=%s", data.get('tran_id'))

        try:
            gateway = get_payment_gateway('sslcommerz')
            # Step 1: Verify IPN authenticity
            gateway.verify_ipn(dict(data), dict(request.headers))
        except InvalidIPNSignature as exc:
            logger.warning("SSLCommerz IPN signature invalid: %s", exc)
            return Response({'status': 'invalid'}, status=status.HTTP_400_BAD_REQUEST)

        # Step 2: Extract payment data
        tran_id = data.get('tran_id')          # Our invoice_number
        val_id = data.get('val_id')
        amount = Decimal(str(data.get('amount', '0')))
        gateway_txn_id = data.get('bank_tran_id', val_id)

        # Step 3: Find the invoice by invoice_number (tran_id)
        try:
            invoice = Invoice.objects.get(invoice_number=tran_id)
        except Invoice.DoesNotExist:
            logger.error("SSLCommerz IPN: Invoice not found for tran_id=%s", tran_id)
            return Response({'status': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        # Step 4: Confirm payment (idempotent)
        try:
            PaymentService.confirm_payment(
                invoice_id=str(invoice.id),
                gateway='sslcommerz',
                gateway_transaction_id=gateway_txn_id,
                amount=amount,
                gateway_response=dict(data),
            )
            logger.info("SSLCommerz payment confirmed for invoice %s", invoice.invoice_number)
        except Exception as exc:
            logger.error("SSLCommerz payment confirmation failed: %s", exc, exc_info=True)
            return Response({'status': 'error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # SSLCommerz expects 200 OK with plain text
        return Response({'status': 'VALID'}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class BKashCallbackView(APIView):
    """
    POST /api/v1/billing/ipn/bkash/
    bKash redirect callback after customer payment.
    bKash redirects the customer here with paymentID + status in query params.

    Security: We verify by calling bKash query API (not trusting URL params alone).
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        payment_id = request.query_params.get('paymentID') or request.data.get('paymentID')
        status_param = request.query_params.get('status', '')

        logger.info("bKash callback received: paymentID=%s status=%s", payment_id, status_param)

        if status_param in ('cancel', 'failure') or not payment_id:
            return Response({'status': 'cancelled'}, status=status.HTTP_200_OK)

        try:
            gateway = BKashGateway()

            # Step 1: Execute (capture) the payment
            execute_result = gateway.execute_payment(payment_id)
            logger.info("bKash execute result: %s", execute_result)

            if execute_result.get('statusCode') != '0000':
                logger.warning(
                    "bKash execute failed for paymentID=%s: %s",
                    payment_id, execute_result.get('statusMessage')
                )
                return Response({'status': 'failed'}, status=status.HTTP_400_BAD_REQUEST)

            # Step 2: Extract data from execute response
            trx_id = execute_result.get('trxID')
            merchant_invoice = execute_result.get('merchantInvoiceNumber')
            amount = Decimal(str(execute_result.get('amount', '0')))

            # Step 3: Find invoice by invoice_number (merchantInvoiceNumber)
            invoice = Invoice.objects.get(invoice_number=merchant_invoice)

            # Step 4: Confirm payment
            PaymentService.confirm_payment(
                invoice_id=str(invoice.id),
                gateway='bkash',
                gateway_transaction_id=trx_id,
                amount=amount,
                gateway_response=execute_result,
            )
            logger.info("bKash payment confirmed: trxID=%s invoice=%s", trx_id, merchant_invoice)
            return Response({'status': 'success', 'trxID': trx_id})

        except Invoice.DoesNotExist:
            logger.error("bKash callback: Invoice not found for paymentID=%s", payment_id)
            return Response({'status': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.error("bKash callback error: %s", exc, exc_info=True)
            return Response({'status': 'error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
