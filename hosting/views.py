"""
Hosting Views
==============
Package listing, account ordering, and client account management endpoints.
"""
import logging
from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache
from drf_spectacular.utils import extend_schema

from core.cache import make_cache_key, TTL_HOSTING_PACKAGES, TTL_CLIENT_DASHBOARD
from .models import HostingPackage, HostingAccount
from .serializers import (
    HostingPackageSerializer, HostingAccountSerializer, OrderHostingSerializer
)
from .services import ProvisioningService
from billing.services import InvoiceService

logger = logging.getLogger('hosting')


class HostingPackageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/hosting/packages/      — Public package catalogue (cached 10 min)
    GET /api/v1/hosting/packages/{id}/ — Single package detail
    """
    serializer_class = HostingPackageSerializer
    permission_classes = [permissions.AllowAny]  # Package list is public
    queryset = HostingPackage.objects.filter(is_active=True).select_related('server')

    def list(self, request, *args, **kwargs):
        """Cache the package list — it rarely changes."""
        cache_key = make_cache_key('hosting_packages')
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=TTL_HOSTING_PACKAGES)
        return response


class HostingAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/v1/hosting/accounts/      — List client's hosting accounts
    GET /api/v1/hosting/accounts/{id}/ — Account detail
    POST /api/v1/hosting/accounts/{id}/order/ — Place a new hosting order
    """
    serializer_class = HostingAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Scoped to current user.
        select_related/prefetch avoids N+1 on package + server + user.
        """
        return (
            HostingAccount.objects
            .filter(user=self.request.user)
            .select_related('package', 'server')
            .order_by('-created_at')
        )


class OrderHostingView(generics.CreateAPIView):
    """
    POST /api/v1/hosting/order/
    Place a new hosting order. Creates a PENDING account + unpaid invoice.
    The account is provisioned automatically after payment.
    """
    serializer_class = OrderHostingSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary='Place a hosting order', tags=['Hosting'])
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        package = serializer.validated_data['package_id']   # Resolved to instance by serializer
        domain = serializer.validated_data['domain']
        billing_cycle = serializer.validated_data['billing_cycle']

        # 1. Create PENDING account record
        account = ProvisioningService.create_pending_account(
            user=request.user,
            package=package,
            domain=domain,
            billing_cycle=billing_cycle,
        )

        # 2. Create unpaid invoice for the order
        invoice = InvoiceService.create_hosting_invoice(
            user=request.user,
            hosting_account=account,
            amount=account.amount,
            description=f'Hosting: {domain} ({package.name})',
            due_days=7,
        )

        logger.info(
            "Order placed: domain=%s package=%s invoice=%s",
            domain, package.name, invoice.invoice_number
        )

        return Response(
            {
                'account_id': str(account.id),
                'invoice_number': invoice.invoice_number,
                'invoice_id': str(invoice.id),
                'amount': str(invoice.total),
                'message': 'Order placed. Pay your invoice to activate the account.',
            },
            status=status.HTTP_201_CREATED
        )
