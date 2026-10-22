"""Passenger WSGI configuration for the cPanel Python application."""
import logging
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')

try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception:
    # Keep diagnostic details in server logs, never in public HTTP responses.
    logging.getLogger(__name__).exception("Django failed to start")

    def application(environ, start_response):
        body = (
            '<!doctype html><html lang="en"><head><title>Service temporarily unavailable</title>'
            '</head><body><h1>Service temporarily unavailable</h1>'
            '<p>Please try again later.</p></body></html>'
        ).encode('utf-8')
        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body))),
        ])
        return [body]
