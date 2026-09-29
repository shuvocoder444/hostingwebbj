"""
Billing Serializers
====================
"""
from rest_framework import serializers
from .models import Invoice, InvoiceItem, Transaction


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ['id', 'description', 'quantity', 'unit_price', 'line_total']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            'id', 'gateway', 'status',
            'gateway_transaction_id', 'amount', 'created_at',
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    """Summary serializer for invoice lists (cached)."""

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_type', 'status',
            'total', 'currency', 'issued_date', 'due_date', 'paid_at',
        ]


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with nested line items and transaction history."""
    items = InvoiceItemSerializer(many=True, read_only=True)
    transactions = TransactionSerializer(many=True, read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_type', 'status', 'is_overdue',
            'subtotal', 'tax_percent', 'tax_amount', 'discount_amount',
            'total', 'currency',
            'issued_date', 'due_date', 'paid_at', 'notes',
            'items', 'transactions',
        ]

    def get_is_overdue(self, obj: Invoice) -> bool:
        return obj.is_overdue
