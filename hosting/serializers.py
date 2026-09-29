"""
Hosting Serializers
====================
"""
from rest_framework import serializers
from .models import Server, HostingPackage, HostingAccount


class HostingPackageSerializer(serializers.ModelSerializer):
    """Public-facing package list — no server internals exposed."""

    class Meta:
        model = HostingPackage
        fields = [
            'id', 'name', 'disk_quota_mb', 'bandwidth_mb',
            'max_databases', 'max_email_accounts', 'max_subdomains',
            'monthly_price', 'quarterly_price', 'semi_annual_price', 'annual_price',
            'setup_fee', 'description', 'is_featured',
        ]


class HostingAccountSerializer(serializers.ModelSerializer):
    """Account list — current user's accounts with nested package info."""
    package_name = serializers.CharField(source='package.name', read_only=True)
    billing_cycle_display = serializers.CharField(
        source='get_billing_cycle_display', read_only=True
    )

    class Meta:
        model = HostingAccount
        fields = [
            'id', 'domain', 'username', 'status',
            'package_name', 'billing_cycle', 'billing_cycle_display',
            'amount', 'provisioned_at', 'next_due_date', 'created_at',
        ]
        read_only_fields = fields  # Accounts created via order flow, not direct API


class OrderHostingSerializer(serializers.Serializer):
    """
    Input serializer for placing a hosting order.
    Validates package selection, domain, and billing cycle.
    """
    package_id = serializers.UUIDField()
    domain = serializers.CharField(max_length=255)
    billing_cycle = serializers.ChoiceField(choices=[
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
    ])

    def validate_domain(self, value: str) -> str:
        """Basic domain format check and uniqueness validation."""
        import re
        domain = value.lower().strip()
        pattern = r'^(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$'
        if not re.match(pattern, domain):
            raise serializers.ValidationError(
                f"'{value}' is not a valid domain name."
            )
        if HostingAccount.objects.filter(domain=domain).exists():
            raise serializers.ValidationError(
                f"Domain '{domain}' is already registered on this platform."
            )
        return domain

    def validate_package_id(self, value) -> HostingPackage:
        """Resolve UUID to active HostingPackage instance."""
        try:
            return HostingPackage.objects.select_related('server').get(
                id=value, is_active=True
            )
        except HostingPackage.DoesNotExist:
            raise serializers.ValidationError("Package not found or is no longer available.")
