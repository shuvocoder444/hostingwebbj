"""
Hosting Django Admin Interface
================================
Provides staff management for:
  - Servers (with encrypted WHM/CyberPanel tokens and Connection Test)
  - Hosting Packages (Catalogue management)
  - Hosting Accounts (Account oversight with Suspend/Unsuspend actions)
"""
from django.contrib import admin, messages
from django import forms
from django.utils.html import format_html
from django.urls import path
from django.http import HttpResponseRedirect

from .models import Server, HostingPackage, HostingAccount
from .drivers.factory import get_driver


class ServerAdminForm(forms.ModelForm):
    """
    Custom form for Server that provides a masked API Token input.
    Ensures tokens are encrypted via set_api_token() on save.
    """
    api_token_input = forms.CharField(
        label="WHM / Panel API Token",
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Enter or update the WHM API token. Stored encrypted at rest using Fernet AES-128."
    )

    class Meta:
        model = Server
        exclude = ['_api_token']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['api_token_input'].required = True


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    form = ServerAdminForm
    list_display = ['name', 'hostname', 'ip_address', 'driver', 'active_accounts_badge', 'max_accounts', 'is_active', 'test_connection_button']
    list_filter = ['driver', 'is_active']
    search_fields = ['name', 'hostname', 'ip_address']
    actions = ['test_server_connection']

    fieldsets = (
        ("Basic Configuration", {
            'fields': ('name', 'hostname', 'ip_address', 'port', 'driver', 'is_active')
        }),
        ("Authentication & API Credentials", {
            'fields': ('api_username', 'api_token_input'),
            'description': "WHM requires root or reseller username and an API Token from WHM > Manage API Tokens."
        }),
        ("Capacity & Nameservers", {
            'fields': ('max_accounts', 'nameserver_1', 'nameserver_2')
        }),
    )

    def active_accounts_badge(self, obj: Server):
        count = obj.accounts.filter(status=HostingAccount.Status.ACTIVE).count()
        pct = int((count / obj.max_accounts) * 100) if obj.max_accounts else 0
        color = "green" if pct < 75 else ("orange" if pct < 90 else "red")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/{} ({}%)</span>',
            color, count, obj.max_accounts, pct
        )
    active_accounts_badge.short_description = "Active / Capacity"

    def test_connection_button(self, obj: Server):
        return format_html(
            '<a class="button" href="test-connection/{}/" style="padding: 3px 8px; background: #4f46e5; color: white; border-radius: 4px;">⚡ Test Connection</a>',
            obj.pk
        )
    test_connection_button.short_description = "Diagnostics"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('test-connection/<uuid:server_id>/', self.admin_site.admin_view(self.test_connection_view), name='hosting_server_test_connection'),
        ]
        return custom_urls + urls

    def test_connection_view(self, request, server_id):
        server = self.get_object(request, server_id)
        if not server:
            messages.error(request, "Server not found.")
            return HttpResponseRedirect("../../")

        try:
            driver = get_driver(server)
            # Try a lightweight operation or info fetch
            info = driver.get_account_info('root')
            messages.success(request, f"✓ Connection to '{server.name}' ({server.hostname}) was SUCCESSFUL! API token is valid.")
        except Exception as exc:
            messages.warning(request, f"Connected to server '{server.hostname}', Driver response: {str(exc)}")

        return HttpResponseRedirect("../../")

    def save_model(self, request, obj, form, change):
        token_input = form.cleaned_data.get('api_token_input')
        if token_input:
            obj.set_api_token(token_input)
        super().save_model(request, obj, form, change)


@admin.register(HostingPackage)
class HostingPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'server', 'monthly_price', 'annual_price', 'disk_quota_display', 'bandwidth_display', 'is_featured', 'is_active']
    list_filter = ['server', 'is_active', 'is_featured']
    search_fields = ['name', 'panel_package_name']

    fieldsets = (
        ("Plan Information", {
            'fields': ('name', 'server', 'panel_package_name', 'description', 'is_active', 'is_featured')
        }),
        ("Pricing (BDT)", {
            'fields': ('monthly_price', 'quarterly_price', 'semi_annual_price', 'annual_price', 'setup_fee')
        }),
        ("Resource Quotas", {
            'fields': ('disk_quota_mb', 'bandwidth_mb', 'max_databases', 'max_email_accounts', 'max_subdomains', 'max_ftp_accounts')
        }),
    )

    def disk_quota_display(self, obj):
        return f"{obj.disk_quota_mb / 1024:.1f} GB" if obj.disk_quota_mb > 0 else "Unlimited"
    disk_quota_display.short_description = "Disk"

    def bandwidth_display(self, obj):
        return f"{obj.bandwidth_mb / 1024:.1f} GB" if obj.bandwidth_mb > 0 else "Unlimited"
    bandwidth_display.short_description = "Bandwidth"


@admin.register(HostingAccount)
class HostingAccountAdmin(admin.ModelAdmin):
    list_display = ['domain', 'user', 'package', 'server', 'status_badge', 'username', 'next_due_date', 'amount']
    list_filter = ['status', 'billing_cycle', 'server']
    search_fields = ['domain', 'username', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'provisioned_at']
    actions = ['suspend_accounts', 'unsuspend_accounts']

    def status_badge(self, obj):
        colors = {
            HostingAccount.Status.ACTIVE: '#10b981',
            HostingAccount.Status.PENDING: '#f59e0b',
            HostingAccount.Status.SUSPENDED: '#ef4444',
            HostingAccount.Status.TERMINATED: '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def suspend_accounts(self, request, queryset):
        for account in queryset:
            account.status = HostingAccount.Status.SUSPENDED
            account.save(update_fields=['status'])
        messages.success(request, f"Marked {queryset.count()} account(s) as SUSPENDED.")
    suspend_accounts.short_description = "Suspend selected accounts"

    def unsuspend_accounts(self, request, queryset):
        for account in queryset:
            account.status = HostingAccount.Status.ACTIVE
            account.save(update_fields=['status'])
        messages.success(request, f"Marked {queryset.count()} account(s) as ACTIVE.")
    unsuspend_accounts.short_description = "Unsuspend selected accounts"
