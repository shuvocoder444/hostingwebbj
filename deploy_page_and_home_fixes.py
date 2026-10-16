import os
import paramiko
import time

FILES_TO_UPLOAD = [
    'hosting/models.py',
    'hosting/migrations/0006_alter_hostingpackage_target_page.py',
    'core/page_views.py',
    'core/views.py',
    'core/sitemaps.py',
    'hostpro/urls.py',
    'templates/base.html',
    'templates/index.html',
    'templates/pages/hosting_germany.html',
    'templates/pages/hosting_finland.html',
]

TARGET_DIR = '/home/webkoders/velohoster.com'
PYTHON_BIN = '/home/webkoders/virtualenv/velohoster.com/3.12/bin/python'

REMOTE_SEED_SCRIPT = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()

from hosting.models import PackageCategory

categories_data = [
    {'name': 'Domain & Hosting OFFER', 'slug': 'domain-hosting-offer', 'sort_order': 1, 'description': 'Exclusive combo packages with free domain and heavy discounts'},
    {'name': 'Premium Hosting', 'slug': 'premium-hosting', 'sort_order': 2, 'description': 'Dedicated resource hosting for business portals'},
    {'name': 'USA Hosting', 'slug': 'usa-hosting', 'sort_order': 3, 'description': 'Fast NVMe SSD hosting with global CDN presence'},
    {'name': 'Singapore Hosting', 'slug': 'singapore-hosting', 'sort_order': 4, 'description': 'Low latency Asian cloud infrastructure'},
    {'name': 'Germany Hosting', 'slug': 'germany-hosting', 'sort_order': 5, 'description': 'Frankfurt European hub with 10Gbps DE-CIX peering'},
    {'name': 'Finland Hosting', 'slug': 'finland-hosting', 'sort_order': 6, 'description': 'Helsinki Nordic cloud powered by 100% green energy'},
    {'name': 'BDIX Hosting', 'slug': 'bdix-hosting', 'sort_order': 7, 'description': 'Ultra-low 1-5ms ping server hosting across Bangladesh'},
    {'name': 'VPS Hosting', 'slug': 'vps-hosting', 'sort_order': 8, 'description': 'Managed Cloud KVM VPS Hosting'}
]

for d in categories_data:
    cat, created = PackageCategory.objects.update_or_create(slug=d['slug'], defaults=d)
    print(f"{'Created' if created else 'Updated'} category: {cat.name} ({cat.slug})")

print('Remote category synchronization complete.')
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
    
    connected = False
    for attempt in range(1, 4):
        try:
            print(f"  Connection attempt {attempt}...", flush=True)
            ssh.connect("195.250.26.201", username="webkoders", pkey=key, port=22, timeout=45, banner_timeout=90)
            connected = True
            break
        except Exception as e:
            print(f"  Attempt {attempt} failed: {e}", flush=True)
            time.sleep(3)
    
    if not connected:
        raise RuntimeError("Failed to connect after 3 attempts.")
    
    sftp = ssh.open_sftp()

    print(f"\nUploading updated files to {TARGET_DIR}...", flush=True)
    for rel_path in FILES_TO_UPLOAD:
        if os.path.exists(rel_path):
            remote_file = f"{TARGET_DIR}/{rel_path}"
            remote_dir = os.path.dirname(remote_file)
            try:
                sftp.stat(remote_dir)
            except IOError:
                run_cmd(ssh, f"mkdir -p {remote_dir}")
            
            sftp.put(rel_path, remote_file)
            print(f"  Uploaded: {rel_path}", flush=True)
        else:
            print(f"  WARNING: Local file not found: {rel_path}", flush=True)

    print("\nRunning database migrations on remote server...", flush=True)
    code, out, err = run_cmd(ssh, f"cd {TARGET_DIR} && {PYTHON_BIN} manage.py migrate hosting")
    print(f"Migrate output:\n{out}\n{err}")

    print("\nSynchronizing package categories on remote server...", flush=True)
    with sftp.open(f"{TARGET_DIR}/seed_new_categories.py", "w") as f:
        f.write(REMOTE_SEED_SCRIPT)
    code, out, err = run_cmd(ssh, f"cd {TARGET_DIR} && {PYTHON_BIN} seed_new_categories.py")
    print(f"Seed output:\n{out}\n{err}")
    run_cmd(ssh, f"rm -f {TARGET_DIR}/seed_new_categories.py")

    print("\nClearing cache...", flush=True)
    clear_script = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()
from django.core.cache import cache
cache.clear()
print('Cache cleared successfully.')
"""
    with sftp.open(f"{TARGET_DIR}/clear_cache.py", "w") as f:
        f.write(clear_script)
    code, out, err = run_cmd(ssh, f"cd {TARGET_DIR} && {PYTHON_BIN} clear_cache.py")
    print(f"Cache clear output: {out.strip()} {err.strip()}")
    run_cmd(ssh, f"rm -f {TARGET_DIR}/clear_cache.py")

    print("\nCollecting static files...", flush=True)
    code, out, err = run_cmd(ssh, f"cd {TARGET_DIR} && {PYTHON_BIN} manage.py collectstatic --noinput")
    print(f"Collectstatic output: {out.strip()}")

    print("\nRestarting Passenger application...", flush=True)
    run_cmd(ssh, f"touch {TARGET_DIR}/tmp/restart.txt")
    print("[OK] Passenger application reloaded.")

    sftp.close()
    ssh.close()
    print("\nDeployment completed successfully!", flush=True)

if __name__ == '__main__':
    deploy()

