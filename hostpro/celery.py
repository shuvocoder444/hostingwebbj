"""
Celery Application Configuration
==================================
This module creates the Celery application used throughout HostPro.
Import it in __init__.py so Celery is always initialized when Django starts.
"""
import os
from celery import Celery

# Tell Celery which Django settings module to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')

app = Celery('hostpro')

# Load config from Django settings, namespace all CELERY_ keys
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py in every INSTALLED_APP
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Healthcheck task — print request info."""
    print(f'Request: {self.request!r}')
