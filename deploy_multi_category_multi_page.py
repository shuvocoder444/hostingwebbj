import os
import time

import paramiko

FILES_TO_UPLOAD = [
    'hosting/models.py',
    'hosting/migrations/0007_hostingpackage_categories_and_more.py',
    'core/views.py',
    'core/admin_views.py',
    'templates/admin_dashboard.html',
    'templates/index.html',
]

TARGET_DIR = '/home/webkoders/velohoster.com'
PYTHON_BIN = '/home/webkoders/virtualenv/velohoster.com/3.12/bin/python'

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

    print(f"\nUploading files to {TARGET_DIR}...", flush=True)
    for rel_path in FILES_TO_UPLOAD:
        if os.path.exists(rel_path):
            remote_file = f"{TARGET_DIR}/{rel_path}"
            remote_dir = os.path.dirname(remote_file)
            try:
                sftp.stat(remote_dir)
            except OSError:
                run_cmd(ssh, f"mkdir -p {remote_dir}")
            
            sftp.put(rel_path, remote_file)
            print(f"  Uploaded: {rel_path}", flush=True)
        else:
            print(f"  Warning: Local file not found: {rel_path}", flush=True)

    sftp.close()

    print("\nRunning database migration on remote...", flush=True)
    code, out, err = run_cmd(ssh, f"{PYTHON_BIN} {TARGET_DIR}/manage.py migrate")
    print(f"Migrate output:\n{out}\n{err}")

    print("\nBackfilling remote package data...", flush=True)
    backfill_cmd = (
        PYTHON_BIN + ' ' + TARGET_DIR + '/manage.py shell << \'EOF\'\n'
        'from hosting.models import HostingPackage\n'
        'all_hosting_pages = ["usa", "singapore", "germany", "finland", "bdix", "vps", "turbo", "premium", "reseller"]\n'
        'for p in HostingPackage.objects.all():\n'
        '    if p.category:\n'
        '        p.categories.add(p.category)\n'
        '    if not p.target_pages:\n'
        '        if p.target_page == "all":\n'
        '            p.target_pages = all_hosting_pages\n'
        '        elif p.target_page:\n'
        '            p.target_pages = [p.target_page]\n'
        '        else:\n'
        '            p.target_pages = ["home"]\n'
        '        p.save()\n'
        '    print("Synced", p.name, "target_pages:", p.target_pages, "categories:", [c.name for c in p.categories.all()])\n'
        'EOF\n'
    )
    code, out, err = run_cmd(ssh, backfill_cmd)
    print(f"Backfill output:\n{out}\n{err}")

    print("\nClearing cache...", flush=True)
    code, out, err = run_cmd(ssh, f"{PYTHON_BIN} {TARGET_DIR}/manage.py clear_cache")
    print(f"Cache clear output: {out} {err}")

    print("\nCollecting static files...", flush=True)
    code, out, err = run_cmd(ssh, f"{PYTHON_BIN} {TARGET_DIR}/manage.py collectstatic --noinput")
    print(f"Collectstatic output: {out}")

    print("\nRestarting Passenger application...", flush=True)
    code, out, err = run_cmd(ssh, f"touch {TARGET_DIR}/tmp/restart.txt")
    if code == 0:
        print("[OK] Passenger application reloaded.")
    else:
        print(f"[ERR] Failed to touch restart.txt: {err}")

    ssh.close()
    print("\nDeployment completed successfully!")

if __name__ == '__main__':
    deploy()
