import os
import time

import paramiko

FILES_TO_UPLOAD = [
    'core/views.py',
    'templates/base.html',
    'templates/pages/hosting_usa.html',
    'templates/pages/hosting_singapore.html',
    'templates/pages/hosting_germany.html',
    'templates/pages/hosting_finland.html',
    'templates/pages/hosting_bdix.html',
    'templates/pages/hosting_vps.html',
    'templates/pages/hosting_premium.html',
    'templates/pages/hosting_turbo_cloud.html',
    'templates/pages/hosting_reseller.html',
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

    print(f"\nUploading updated templates and views to {TARGET_DIR}...", flush=True)
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
            print(f"  WARNING: Local file not found: {rel_path}", flush=True)

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
