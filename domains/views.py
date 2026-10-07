"""
Domains Views & Endpoints
==========================
Public domain availability search & Client domain management.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Domain, TLDPricing
from .serializers import DomainSerializer, TLDPricingSerializer, OrderDomainSerializer
from .services import DomainService
from billing.services import InvoiceService


class DomainSearchView(APIView):
    """
    GET /api/v1/domains/search/?domain=example.com
    Check domain availability and retail price against Wholesale Registrar.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary='Check domain availability and pricing',
        tags=['Domains'],
        parameters=[OpenApiParameter('domain', str, description='Domain to search, e.g. "mybrand.com"')]
    )
    def get(self, request):
        domain_query = request.query_params.get('domain', '').strip()
        if not domain_query:
            return Response({'error': 'Parameter "domain" is required.'}, status=status.HTTP_400_BAD_REQUEST)

        result = DomainService.check_availability(domain_query)
        suggestions = []
        if not result.is_available:
            suggestions = DomainService.get_suggestions(domain_query, max_results=5)

        return Response({
            'domain': result.domain,
            'is_available': result.is_available,
            'status': result.status,
            'price': str(result.price),
            'currency': result.currency,
            'message': result.message,
            'suggestions': suggestions,
        })



class TLDPricingListView(APIView):
    """
    GET /api/v1/domains/pricing/
    Returns active TLD pricing catalogue.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary='List TLD prices', tags=['Domains'])
    def get(self, request):
        tlds = TLDPricing.objects.filter(is_active=True).order_by('register_price')
        serializer = TLDPricingSerializer(tlds, many=True)
        return Response(serializer.data)


class DomainViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/domains/       — List client domains
    GET /api/v1/domains/{id}/  — Domain detail
    """
    serializer_class = DomainSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Domain.objects.filter(user=self.request.user).order_by('-created_at')


class OrderDomainAPIView(APIView):
    """
    POST /api/v1/domains/order/
    Create a pending domain registration and return the generated invoice.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary='Order a domain', tags=['Domains'])
    def post(self, request):
        serializer = OrderDomainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        domain_name = data['domain']
        years = data.get('years', 1)

        # Check availability
        check = DomainService.check_availability(domain_name)
        if not check.is_available:
            return Response({'detail': f"Domain '{domain_name}' is not available."}, status=status.HTTP_400_BAD_REQUEST)

        # Create Pending Domain
        domain = DomainService.create_pending_domain(
            user=request.user,
            domain_name=domain_name,
            years=years,
            nameservers=[data.get('nameserver_1'), data.get('nameserver_2')],
        )

        # Create Invoice
        invoice = InvoiceService.create_domain_invoice(
            user=request.user,
            domain=domain,
            amount=check.price * years,
            description=f"Domain Registration: {domain.domain_name} ({years} Year)",
        )

        return Response({
            'domain_id': domain.id,
            'domain_name': domain.domain_name,
            'status': domain.status,
            'invoice_id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'total': str(invoice.total),
            'currency': invoice.currency,
        }, status=status.HTTP_201_CREATED)


@login_required(login_url='login')
@require_http_methods(['POST'])
def order_domain_web_view(request):
    """
    Web form POST endpoint from landing page or dashboard to order a domain.
    Creates Pending Domain + Unpaid Invoice and redirects to dashboard.
    """
    domain_name = request.POST.get('domain', '').strip().lower()
    years = int(request.POST.get('years', 1))

    if not domain_name:
        messages.error(request, 'Please provide a valid domain name.')
        return redirect('dashboard')

    check = DomainService.check_availability(domain_name)
    if not check.is_available:
        messages.error(request, f"The domain '{domain_name}' is already taken or unavailable.")
        return redirect('dashboard')

    try:
        domain = DomainService.create_pending_domain(
            user=request.user,
            domain_name=domain_name,
            years=years,
        )

        total_amount = check.price * years
        invoice = InvoiceService.create_domain_invoice(
            user=request.user,
            domain=domain,
            amount=total_amount,
            description=f"Domain Registration: {domain.domain_name} ({years} Year)",
        )

        messages.success(
            request,
            f"Domain '{domain.domain_name}' added to your account! "
            f"Invoice #{invoice.invoice_number} (BDT {invoice.total}) generated. Pay now for instant activation."
        )
    except Exception as exc:
        messages.error(request, f"Failed to order domain: {str(exc)}")

    return redirect('dashboard')
