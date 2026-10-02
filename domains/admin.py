"""
Domains Django Admin Interface
================================
Staff management for:
  - Wholesale Registrars (ResellerClub, Namecheap with live Balance Check)
  - TLD Pricing Catalogue (.com, .net, .org, .com.bd)
  - Client Domain Portfolios
"""
from django.contrib import admin, messages
from django import forms
from django.utils.html import format_html
from django.urls import path
from django.http import HttpResponseRedirect

from .models import DomainRegistrar, TLDPricing, Domain
from .drivers.factory import get_registrar_driver


class DomainRegistrarAdminForm(forms.ModelForm):
    """Masked API key input for domain registrars."""
    api_key_input = forms.CharField(
        label="Registrar API Key / Secret",
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Wholesale API key provided by ResellerClub or Namecheap. Encrypted at rest via Fernet."
    )

    class Meta:
        model = DomainRegistrar
        exclude = ['_api_key']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['api_key_input'].required = True


@admin.register(DomainRegistrar)
class DomainRegistrarAdmin(admin.ModelAdmin):
    form = DomainRegistrarAdminForm
    list_display = ['name', 'driver', 'api_user', 'sandbox_badge', 'is_active', 'is_default', 'check_balance_button']
    list_filter = ['driver', 'is_sandbox', 'is_active']
    search_fields = ['name', 'api_user']

    fieldsets = (
        ("Registrar Details", {
            'fields': ('name', 'driver', 'is_sandbox', 'is_active', 'is_default')
        }),
        ("API Authentication", {
            'fields': ('api_user', 'api_key_input', 'extra_config'),
            'description': "ResellerClub requires your Reseller ID as api_user. Namecheap requires ApiUser and whitelisted IP in extra_config."
        }),
    )

    def sandbox_badge(self, obj):
        bg, text = ('#f59e0b', 'SANDBOX') if obj.is_sandbox else ('#10b981', 'LIVE')
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px;">{}</span>', bg, text)
    sandbox_badge.short_description = "Environment"

    def check_balance_button(self, obj):
        return format_html(
            '<a class="button" href="check-balance/{}/" style="padding: 2px 8px; background: #059669; color: white; border-radius: 4px;">💰 Check Balance</a>',
            obj.pk
        )
    check_balance_button.short_description = "Balance"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('check-balance/<uuid:registrar_id>/', self.admin_site.admin_view(self.check_balance_view), name='domain_registrar_check_balance'),
        ]
        return custom + urls

    def check_balance_view(self, request, registrar_id):
        registrar = self.get_object(request, registrar_id)
        if not registrar:
            messages.error(request, "Registrar not found.")
            return HttpResponseRedirect("../../")

        try:
            driver = get_registrar_driver(registrar)
            bal_data = driver.get_account_balance()
            messages.success(request, f"✓ {registrar.name} Live Balance: {bal_data.get('currency', 'USD')} {bal_data.get('balance', '0.00')}")
        except Exception as exc:
            messages.warning(request, f"Could not fetch balance: {str(exc)}")

        return HttpResponseRedirect("../../")

    def save_model(self, request, obj, form, change):
        key = form.cleaned_data.get('api_key_input')
        if key:
            obj.set_api_key(key)
        super().save_model(request, obj, form, change)


@admin.register(TLDPricing)
class TLDPricingAdmin(admin.ModelAdmin):
    list_display = ['tld', 'registrar', 'register_price', 'renew_price', 'currency', 'is_featured', 'is_active']
    list_filter = ['is_active', 'is_featured', 'registrar']
    list_editable = ['register_price', 'renew_price', 'is_active']
    search_fields = ['tld']


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['domain_name', 'user', 'registrar', 'status_badge', 'registration_date', 'expiry_date', 'auto_renew']
    list_filter = ['status', 'auto_renew', 'registrar']
    search_fields = ['domain_name', 'user__email', 'registrar_order_id']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['register_now_action', 'set_active_action']

    def status_badge(self, obj):
        colors = {
            Domain.Status.ACTIVE: '#10b981',
            Domain.Status.PENDING: '#f59e0b',
            Domain.Status.EXPIRED: '#ef4444',
            Domain.Status.SUSPENDED: '#dc2626',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def register_now_action(self, request, queryset):
        from domains.services import DomainService
        success = 0
        for domain in queryset:
            try:
                DomainService.provision_domain(str(domain.id))
                success += 1
            except Exception as exc:
                messages.error(request, f"Error provisioning {domain.domain_name}: {exc}")
        if success:
            messages.success(request, f"Successfully provisioned {success} domain(s) at the registrar!")
    register_now_action.short_description = "Register at Registrar API Now"

    def set_active_action(self, request, queryset):
        queryset.update(status=Domain.Status.ACTIVE)
        messages.success(request, f"Marked {queryset.count()} domain(s) as ACTIVE.")
    set_active_action.short_description = "Set status to ACTIVE"
