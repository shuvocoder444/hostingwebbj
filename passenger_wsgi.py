"""
Passenger WSGI Configuration for cPanel Python App
===================================================
Bridges Phusion Passenger to Django's WSGI application.
Captures any startup exceptions and renders them in detail if an error occurs.
"""
import os
import sys

# 1. Add application directory to Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# 2. Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')

# 3. Load WSGI application with startup diagnostic handler
try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception as e:
    import traceback
    error_trace = traceback.format_exc()
    
    def application(environ, start_response):
        status = '500 Internal Server Error'
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>HostPro Application Startup Error</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 30px; }}
        .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 25px; max-width: 900px; margin: 0 auto; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        h1 {{ color: #ef4444; font-size: 22px; margin-top: 0; }}
        pre {{ background: #020617; border: 1px solid #1e293b; padding: 15px; border-radius: 8px; color: #fca5a5; font-size: 13px; line-height: 1.5; overflow-x: auto; white-space: pre-wrap; word-break: break-all; }}
        .info {{ font-size: 14px; color: #94a3b8; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>⚠️ HostPro Python Startup Error</h1>
        <p class="info">Django encountered an error while starting up under Phusion Passenger on your server. See the detailed traceback below:</p>
        <pre>{error_trace}</pre>
    </div>
</body>
</html>"""
        output = html_content.encode('utf-8')
        response_headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(output)))
        ]
        start_response(status, response_headers)
        return [output]
