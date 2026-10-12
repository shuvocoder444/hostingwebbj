import os
import paramiko

FILES_TO_UPLOAD = [
    'hostpro/settings.py',
    'hostpro/urls.py',
    'core/views.py',
    'core/admin_views.py',
    'core/cart_views.py',
    'core/context_processors.py',
    'domains/services.py',
    'domains/views.py',
    'billing/views.py',
    'templates/base.html',
    'templates/index.html',
    'templates/cart_domain.html',
    'templates/cart_configure.html',
    'templates/cart_checkout.html',
]

STATIC_IMAGE_DIR = 'static/images'

TARGET_DOMAINS = [
    '/home/webkoders/velohoster.com',
]

PASSENGER_WSGI_CONTENT = """import os
import sys

# 1. Activate Virtualenv
VENV_LIB = "/home/webkoders/virtualenv/velohoster.com/3.12/lib/python3.12/site-packages"
if VENV_LIB not in sys.path:
    sys.path.insert(0, VENV_LIB)

# 2. Add Project Directory
PROJECT_DIR = "/home/webkoders/velohoster.com"
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)

# 3. Set Settings Module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')

# 4. Load WSGI Application
try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
except Exception as e:
    import traceback
    error_trace = traceback.format_exc()
    def application(environ, start_response):
        status = '500 Internal Server Error'
        body = f\"\"\"<!DOCTYPE html>
<html>
<head><title>VeloHoster Startup Error</title></head>
<body style="font-family: monospace; padding: 25px; background: #0f172a; color: #f8fafc;">
    <h2 style="color: #ef4444;">VeloHoster Application Startup Error</h2>
    <pre style="background: #1e293b; padding: 15px; border-radius: 8px; color: #fca5a5; overflow-x: auto;">{error_trace}</pre>
</body>
</html>\"\"\"
        response_headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body.encode('utf-8'))))]
        start_response(status, response_headers)
        return [body.encode('utf-8')]
"""

HTACCESS_CONTENT = """# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION BEGIN
PassengerAppRoot "/home/webkoders/velohoster.com"
PassengerBaseURI "/"
PassengerPython "/home/webkoders/virtualenv/velohoster.com/3.12/bin/python"
# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION END

# ── LiteSpeed / Apache Browser Caching & Gzip Compression ──
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresDefault "access plus 1 month"
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/jpg "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/webp "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
    ExpiresByType image/x-icon "access plus 1 year"
    ExpiresByType text/css "access plus 1 month"
    ExpiresByType application/javascript "access plus 1 month"
    ExpiresByType font/woff2 "access plus 1 year"
    ExpiresByType font/woff "access plus 1 year"
    ExpiresByType font/ttf "access plus 1 year"
</IfModule>

<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html text/plain text/xml text/css application/javascript application/json
</IfModule>

<IfModule mod_headers.c>
    <FilesMatch "\.(ico|jpe?g|png|gif|webp|svg|woff2?|ttf)$">
        Header set Cache-Control "max-age=31536000, public, immutable"
    </FilesMatch>
    <FilesMatch "\.(css|js)$">
        Header set Cache-Control "max-age=2592000, public"
    </FilesMatch>
</IfModule>
"""

def run_cmd(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, out, err

def deploy():
    print("Connecting to 195.250.26.201 via SSH...", flush=True)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file("C:/Users/shuvo/.ssh/id_rsa", password="SHUVOshuvo123@")
    ssh.connect("195.250.26.201", username="webkoders", pkey=key, port=22, timeout=30, banner_timeout=60)
    
    sftp = ssh.open_sftp()
    
    for base_dir in TARGET_DOMAINS:
        print(f"\nDeploying to {base_dir}...", flush=True)
        
        # Upload main template / code files
        for rel_path in FILES_TO_UPLOAD:
            if os.path.exists(rel_path):
                remote_file = f"{base_dir}/{rel_path}"
                sftp.put(rel_path, remote_file)
                print(f"  Uploaded: {rel_path}", flush=True)

        # Upload static images
        if os.path.exists(STATIC_IMAGE_DIR):
            remote_img_dir = f"{base_dir}/static/images"
            try:
                sftp.mkdir(remote_img_dir)
            except Exception:
                pass
            for img_name in os.listdir(STATIC_IMAGE_DIR):
                local_img = os.path.join(STATIC_IMAGE_DIR, img_name)
                if os.path.isfile(local_img):
                    remote_img = f"{remote_img_dir}/{img_name}"
                    sftp.put(local_img, remote_img)
            print(f"  Uploaded all images from {STATIC_IMAGE_DIR}", flush=True)
                
        py_bin = "/home/webkoders/virtualenv/velohoster.com/3.12/bin/python"
        
        # Write passenger_wsgi.py & .htaccess
        with sftp.open(f"{base_dir}/passenger_wsgi.py", "w") as f:
            f.write(PASSENGER_WSGI_CONTENT)
        print(f"  Updated passenger_wsgi.py", flush=True)

        with sftp.open(f"{base_dir}/.htaccess", "w") as f:
            f.write(HTACCESS_CONTENT)
        print(f"  Updated .htaccess", flush=True)

        # Clear cache
        clear_cache_script = f"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()
from django.core.cache import cache
cache.clear()
print('Cache cleared successfully.')
"""
        with sftp.open(f"{base_dir}/clear_cache.py", "w") as f:
            f.write(clear_cache_script)
            
        code, out, err = run_cmd(ssh, f"cd {base_dir} && {py_bin} clear_cache.py")
        print(f"  [{base_dir}] Cache clear: {out.strip()} {err.strip()}", flush=True)
        run_cmd(ssh, f"rm -f {base_dir}/clear_cache.py")
        
        # Collect static
        run_cmd(ssh, f"{py_bin} {base_dir}/manage.py collectstatic --noinput")
        
        # Restart Passenger
        run_cmd(ssh, f"touch {base_dir}/tmp/restart.txt")
        print(f"[OK] {base_dir} updated and Passenger restarted.", flush=True)
        
    sftp.close()
    ssh.close()
    print("\nCart & Domain updates deployed successfully!", flush=True)

if __name__ == '__main__':
    deploy()
