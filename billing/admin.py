"""
Billing Django Admin Interface
================================
Staff management for Invoices, Transactions, and Payment audit logs.
"""
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils import timezone
from .models import Invoice, InvoiceItem, Transaction


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    fields = ['description', 'quantity', 'unit_price', 'line_total']
    readonly_fields = ['line_total']


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    fields = ['gateway', 'status', 'gateway_transaction_id', 'amount', 'created_at']
    readonly_fields = fields
    can_delete = False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'user', 'invoice_type', 'total_display', 'status_badge', 'issued_date', 'due_date', 'paid_at']
    list_filter = ['status', 'invoice_type', 'issued_date']
    search_fields = ['invoice_number', 'user__email']
    inlines = [InvoiceItemInline, TransactionInline]
    readonly_fields = ['created_at', 'updated_at', 'paid_at']
    actions = ['mark_paid_and_provision', 'mark_overdue']

    def total_display(self, obj):
        return f"৳ {obj.total:,.2f} {obj.currency}"
    total_display.short_description = "Total"

    def status_badge(self, obj):
        colors = {
            Invoice.Status.PAID: '#10b981',
            Invoice.Status.UNPAID: '#f59e0b',
            Invoice.Status.OVERDUE: '#ef4444',
            Invoice.Status.CANCELLED: '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def mark_paid_and_provision(self, request, queryset):
        from billing.services import PaymentService
        import uuid
        count = 0
        for inv in queryset:
            if inv.status != Invoice.Status.PAID:
                PaymentService.confirm_payment(
                    invoice_id=str(inv.id),
                    gateway='manual',
                    gateway_transaction_id=f"MANUAL-{uuid.uuid4().hex[:8].upper()}",
                    amount=inv.total,
                    gateway_response={'status': 'MANUAL_ADMIN_OVERRIDE', 'staff': request.user.email}
                )
                count += 1
        messages.success(request, f"Marked {count} invoice(s) as PAID and triggered automated provisioning!")
    mark_paid_and_provision.short_description = "Mark PAID & Trigger Automated Provisioning"

    def mark_overdue(self, request, queryset):
        queryset.filter(status=Invoice.Status.UNPAID).update(status=Invoice.Status.OVERDUE)
        messages.success(request, f"Updated selected invoices to OVERDUE.")
    mark_overdue.short_description = "Mark as OVERDUE"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['gateway_transaction_id', 'invoice', 'user', 'gateway', 'amount', 'status_badge', 'created_at']
    list_filter = ['gateway', 'status', 'created_at']
    search_fields = ['gateway_transaction_id', 'user__email', 'invoice__invoice_number']
    readonly_fields = ['created_at', 'updated_at', 'gateway_response']

    def status_badge(self, obj):
        colors = {
            Transaction.Status.SUCCESS: '#10b981',
            Transaction.Status.PENDING: '#f59e0b',
            Transaction.Status.FAILED: '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Status"
