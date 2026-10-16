import os
import paramiko

FILES_TO_UPLOAD = [
    'hosting/models.py',
    'hosting/migrations/0004_packagecategory_alter_hostingpackage_options_and_more.py',
    'core/views.py',
    'core/admin_views.py',
    'core/page_views.py',
    'templates/index.html',
    'templates/admin_dashboard.html',
    'templates/pages/hosting_bdix.html',
    'templates/pages/hosting_usa.html',
    'templates/pages/hosting_singapore.html',
    'templates/pages/hosting_premium.html',
    'templates/pages/hosting_turbo_cloud.html',
    'templates/pages/hosting_reseller.html',
    'templates/pages/hosting_vps.html',
]

TARGET_DIR = '/home/webkoders/velohoster.com'
PYTHON_BIN = '/home/webkoders/virtualenv/velohoster.com/3.12/bin/python'

SEED_SCRIPT = """
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()

from hosting.models import PackageCategory, HostingPackage

categories_data = [
    {"name": "Domain & Hosting OFFER", "slug": "domain-hosting-offer", "sort_order": 1, "description": "Exclusive combo packages with free domain and heavy discounts"},
    {"name": "BDIX Hosting", "slug": "bdix-hosting", "sort_order": 2, "description": "Ultra-low 1-5ms ping server hosting across Bangladesh"},
    {"name": "USA Hosting", "slug": "usa-hosting", "sort_order": 3, "description": "Fast NVMe SSD hosting with global CDN presence"},
    {"name": "Singapore Hosting", "slug": "singapore-hosting", "sort_order": 4, "description": "Low latency Asian cloud infrastructure"},
    {"name": "Premium Hosting", "slug": "premium-hosting", "sort_order": 5, "description": "Dedicated resource hosting for business portals"},
]

created_count = 0
for data in categories_data:
    cat, created = PackageCategory.objects.get_or_create(slug=data["slug"], defaults=data)
    if created:
        created_count += 1
        print(f"Created category: {cat.name}")
    else:
        print(f"Category already exists: {cat.name}")

# Link existing packages without category to default category
default_cat = PackageCategory.objects.filter(slug="domain-hosting-offer").first()
if default_cat:
    unassigned = HostingPackage.objects.filter(category__isnull=True)
    count = unassigned.count()
    if count > 0:
        unassigned.update(category=default_cat, target_page='all')
        print(f"Assigned {count} uncategorized packages to '{default_cat.name}'")

print("Seeding completed successfully.")
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
            import time
            time.sleep(3)
    
    if not connected:
        raise RuntimeError("Failed to connect after 3 attempts.")
    
    sftp = ssh.open_sftp()
    
    # Clean up the previous bad migration on remote
    bad_remote_mig = f"{TARGET_DIR}/hosting/migrations/0003_packagecategory_alter_hostingpackage_options_and_more.py"
    run_cmd(ssh, f"rm -f {bad_remote_mig}")
    print(f"Removed old conflict migration on remote server.", flush=True)

    print(f"\nUploading files to {TARGET_DIR}...", flush=True)
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

    print("\nSeeding categories on remote server...", flush=True)
    with sftp.open(f"{TARGET_DIR}/seed_categories.py", "w") as f:
        f.write(SEED_SCRIPT)
    code, out, err = run_cmd(ssh, f"cd {TARGET_DIR} && {PYTHON_BIN} seed_categories.py")
    print(f"Seed output:\n{out}\n{err}")
    run_cmd(ssh, f"rm -f {TARGET_DIR}/seed_categories.py")

    print("\nClearing cache...", flush=True)
    clear_script = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()
from django.core.cache import cache
cache.clear()
print('Cache cleared.')
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
