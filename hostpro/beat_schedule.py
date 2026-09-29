"""
Celery Beat Schedule Configuration
=====================================
Defines all periodic tasks for the HostPro automation engine.

Add this dict to settings.py or run migrations to store in DB via
django-celery-beat (DatabaseScheduler already configured in settings).

Usage: After running migrations, these schedules are auto-loaded.
You can also manage them via Django Admin → Periodic Tasks.
"""
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ── Daily: Generate renewal invoices 7 days before due date ──────────
    'generate-renewal-invoices-daily': {
        'task': 'hosting.generate_renewal_invoices',
        'schedule': crontab(hour=8, minute=0),   # 8:00 AM Asia/Dhaka daily
        'options': {'expires': 3600},             # Task expires after 1hr if not consumed
    },

    # ── Daily: Auto-suspend overdue accounts ──────────────────────────────
    'auto-suspend-overdue-accounts-daily': {
        'task': 'hosting.auto_suspend_overdue_accounts',
        'schedule': crontab(hour=9, minute=0),   # 9:00 AM daily (after invoice marking)
        'options': {'expires': 3600},
    },

    # ── Weekly: Terminate long-suspended accounts (30+ days) ─────────────
    'terminate-long-suspended-weekly': {
        'task': 'hosting.terminate_long_suspended_accounts',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2:00 AM
        'kwargs': {'days_suspended': 30},
        'options': {'expires': 7200},
    },
}
