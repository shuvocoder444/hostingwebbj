from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'billing'
    verbose_name = 'Billing'

    def ready(self):
        """Connect cache invalidation signals after app registry is fully loaded."""
        from core.signals import connect_billing_signals
        connect_billing_signals()
