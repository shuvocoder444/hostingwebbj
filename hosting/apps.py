from django.apps import AppConfig


class HostingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hosting'
    verbose_name = 'Hosting'

    def ready(self):
        """Connect cache invalidation signals after app registry is fully loaded."""
        from core.signals import connect_hosting_signals
        connect_hosting_signals()
