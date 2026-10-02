"""
Domains Serializers
====================
"""
from rest_framework import serializers
from .models import Domain, TLDPricing


class TLDPricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TLDPricing
        fields = ['tld', 'register_price', 'renew_price', 'transfer_price', 'currency', 'is_featured']


class DomainSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Domain
        fields = [
            'id', 'domain_name', 'status', 'status_display',
            'registration_years', 'registration_date', 'expiry_date', 'next_due_date',
            'nameserver_1', 'nameserver_2', 'auto_renew', 'created_at'
        ]
        read_only_fields = fields


class DomainSearchSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=255)


class OrderDomainSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=255)
    years = serializers.IntegerField(default=1, min_value=1, max_value=10)
    nameserver_1 = serializers.CharField(default='ns1.hostpro.bd')
    nameserver_2 = serializers.CharField(default='ns2.hostpro.bd')
