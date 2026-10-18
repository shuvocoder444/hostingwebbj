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
import hashlib
import hmac
import json
import logging
from decimal import Decimal

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from drf_spectacular.utils import extend_schema

from .models import Invoice, Gateway
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
            .select_related('hosting_account', 'domain', 'user')
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


@method_decorator(csrf_exempt, name='dispatch')
class CryptomusIPNView(APIView):
    """
    POST /api/v1/billing/ipn/cryptomus/
    Cryptomus IPN / Webhook Callback.
    Automatic payment verification and instant WHM & domain provisioning!
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        data = request.data
        logger.info("Cryptomus IPN received: order_id=%s, uuid=%s, status=%s", data.get('order_id'), data.get('uuid'), data.get('status'))

        try:
            gateway = get_payment_gateway('cryptomus')
            gateway.verify_ipn(dict(data), dict(request.headers))
        except InvalidIPNSignature as exc:
            logger.warning("Cryptomus IPN signature invalid: %s", exc)
            return Response({'status': 'invalid_signature'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error("Cryptomus IPN verification error: %s", exc)
            return Response({'status': 'error', 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        order_id = data.get('order_id')
        txid = data.get('txid') or data.get('uuid') or f"CRYPTO-{uuid.uuid4().hex[:8].upper()}"
        status_str = str(data.get('status', '')).lower()

        if status_str in ('paid', 'paid_over'):
            try:
                invoice = Invoice.objects.filter(invoice_number=order_id).first()
                if not invoice:
                    invoice = Invoice.objects.filter(id=order_id).first()

                if not invoice:
                    logger.error("Cryptomus IPN: Invoice not found for order_id=%s", order_id)
                    return Response({'status': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

                # Confirm payment in billing service (triggers automatic provisioning of WHM & Domain!)
                PaymentService.confirm_payment(
                    invoice_id=str(invoice.id),
                    gateway='cryptomus',
                    gateway_transaction_id=txid,
                    amount=invoice.total,
                    gateway_response=dict(data),
                )
                logger.info("Cryptomus payment confirmed & auto-provisioning triggered for invoice %s", invoice.invoice_number)
                return Response({'status': 'OK'}, status=status.HTTP_200_OK)

            except Exception as exc:
                logger.error("Cryptomus IPN confirmation error: %s", exc, exc_info=True)
                return Response({'status': 'error', 'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'status': 'ignored', 'payment_status': status_str}, status=status.HTTP_200_OK)


# ─── WebKoders Payment Gateway Webhook & Views ───────────────────────────────

@csrf_exempt
@require_POST
def payment_webhook_view(request):
    """
    Webhook handler for WebKoders Payment Gateway (https://payment.webkoders.com).
    Verifies HMAC-SHA256 signature in X-Signature header before trusting payload.
    When event is 'payment.completed', confirms payment and triggers auto-provisioning!
    """
    secret = ''
    try:
        from core.models import SiteSetting
        site = SiteSetting.get_settings()
        secret = (site.webkoders_api_secret or getattr(settings, 'GATEWAY_API_SECRET', '')).strip()
    except Exception:
        secret = getattr(settings, 'GATEWAY_API_SECRET', '').strip()

    if not secret:
        logger.error("GATEWAY_API_SECRET is not configured on server.")
        return HttpResponse("Server misconfiguration", status=500)

    # 1. Verify HMAC-SHA256 signature over raw request body
    expected = hmac.new(
        secret.encode('utf-8'),
        request.body,
        hashlib.sha256,
    ).hexdigest()

    received = request.headers.get("X-Signature", "") or request.META.get("HTTP_X_SIGNATURE", "")
    if not received or not hmac.compare_digest(expected, received):
        logger.warning("WebKoders webhook signature mismatch. Expected: %s, Received: %s", expected, received)
        return HttpResponse("Invalid signature", status=400)

    # 2. Parse JSON payload
    try:
        event = json.loads(request.body.decode('utf-8'))
    except Exception as exc:
        logger.error("Invalid JSON body in payment webhook: %s", exc)
        return HttpResponse("Invalid JSON", status=400)

    # 3. Only process 'payment.completed' event
    if event.get("event") != "payment.completed":
        logger.info("WebKoders webhook received non-completion event: %s", event.get("event"))
        return HttpResponse(status=200)

    # 4. Resolve Invoice
    order_id = str(event.get("order_id", "")).strip()
    metadata = event.get("metadata") or {}
    local_id = metadata.get("invoice_id") or metadata.get("local_order_id") or order_id

    invoice = None
    try:
        invoice = Invoice.objects.filter(id=local_id).first()
    except Exception:
        pass

    if not invoice and order_id:
        try:
            invoice = Invoice.objects.filter(id=order_id).first()
        except Exception:
            pass

    if not invoice and order_id:
        invoice = Invoice.objects.filter(invoice_number__iexact=order_id).first()

    if not invoice:
        logger.error("WebKoders webhook: Invoice not found for order_id=%s, local_id=%s", order_id, local_id)
        return HttpResponse("Invoice not found", status=404)

    # 5. Check idempotency — if already paid, return 200 immediately
    if invoice.status == Invoice.Status.PAID:
        logger.info("Invoice #%s is already marked PAID. Webhook duplicate ignored.", invoice.invoice_number)
        return HttpResponse(status=200)

    # 6. Verify amount
    raw_amount = event.get("amount")
    try:
        paid_amount = Decimal(str(raw_amount))
    except Exception:
        paid_amount = invoice.total

    if paid_amount < invoice.total:
        logger.error("WebKoders webhook: Underpaid invoice #%s. Expected: %s, Received: %s", invoice.invoice_number, invoice.total, paid_amount)
        return HttpResponse("Amount mismatch", status=400)

    # 7. Extract transaction ID and confirm payment
    trx_id = event.get("transaction_id") or event.get("trx_id") or event.get("reference_id") or event.get("invoice_id") or f"WK-{order_id}"

    try:
        PaymentService.confirm_payment(
            invoice_id=str(invoice.id),
            gateway=Gateway.WEBKODERS if hasattr(Gateway, 'WEBKODERS') else 'webkoders',
            gateway_transaction_id=str(trx_id),
            amount=invoice.total,
            gateway_response=event,
        )
        logger.info("WebKoders payment confirmed & auto-provisioning triggered for Invoice #%s (TrxID: %s)", invoice.invoice_number, trx_id)
    except Exception as exc:
        logger.exception("WebKoders payment confirmation failed for invoice #%s: %s", invoice.invoice_number, exc)
        return HttpResponse(f"Error processing payment: {exc}", status=500)

    return HttpResponse(status=200)


def payment_complete_return_view(request):
    """
    Landing page when customer returns from WebKoders payment gateway.
    """
    order_id = request.GET.get('order_id') or request.GET.get('invoice_id')
    invoice = None
    if order_id:
        try:
            invoice = Invoice.objects.filter(id=order_id).first()
        except Exception:
            pass
        if not invoice:
            invoice = Invoice.objects.filter(invoice_number__iexact=order_id).first()

    if invoice and invoice.status == Invoice.Status.PAID:
        messages.success(
            request,
            f"🎉 Payment successful! Invoice #{invoice.invoice_number} has been settled and your service is now active."
        )
        return redirect('dashboard')
    else:
        messages.info(
            request,
            "Thank you! Your payment is being verified by the gateway. Your invoice status will update automatically momentarily."
        )
        return redirect('/dashboard/?tab=invoices')


@login_required(login_url='login')
def initiate_online_payment_view(request, invoice_id):
    """
    Directly initiates WebKoders Gateway checkout for an invoice and redirects customer to payment gateway.
    """
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    if invoice.status == Invoice.Status.PAID:
        messages.info(request, f"Invoice #{invoice.invoice_number} is already paid.")
        return redirect('/dashboard/?tab=invoices')

    try:
        from core.models import SiteSetting
        site_set = SiteSetting.get_settings()
        gw = get_payment_gateway('webkoders')
        callback_url = getattr(site_set, 'webkoders_webhook_url', None) or request.build_absolute_uri('/payments/webhook/')
        return_url = request.build_absolute_uri(f'/payments/complete/?order_id={invoice.id}')
        res = gw.initiate_payment(
            invoice=invoice,
            customer=request.user,
            callback_url=callback_url,
            return_url=return_url,
        )
        if res and res.get('payment_url'):
            return redirect(res['payment_url'])
        messages.error(request, "Failed to obtain payment URL from gateway.")
    except Exception as exc:
        logger.exception("Error initiating online payment: %s", exc)
        messages.error(request, f"Could not initiate online payment: {exc!s}")

    return redirect(f"/dashboard/?tab=invoices&pay_invoice={invoice.id}")
