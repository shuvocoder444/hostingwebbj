import os
import paramiko

FILES_TO_UPLOAD = [
    'templates/base.html',
    'templates/index.html',
    'templates/cart_domain.html',
    'templates/cart_configure.html',
    'templates/cart_checkout.html',
    'core/cart_views.py',
    'core/context_processors.py',
    'hostpro/urls.py',
]

STATIC_IMAGE_DIR = 'static/images'

TARGET_DOMAINS = [
    '/home/webkoders/velohoster.com',
]

def run_cmd(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
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
                
        py_bin = "/home/webkoders/virtualenv/host.webkoders.com/3.12/bin/python"
        
        # Clear cache and restart passenger
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
