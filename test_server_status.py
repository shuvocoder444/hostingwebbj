import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file("C:/Users/shuvo/.ssh/id_rsa", password="SHUVOshuvo123@")
connected = False
for attempt in range(1, 4):
    try:
        ssh.connect("195.250.26.201", username="webkoders", pkey=key, port=22, timeout=45, banner_timeout=90)
        connected = True
        break
    except Exception as e:
        import time
        time.sleep(3)

if not connected:
    raise RuntimeError("Failed to connect")

cmd = """cd /home/webkoders/velohoster.com && /home/webkoders/virtualenv/velohoster.com/3.12/bin/python - << 'EOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()

from hosting.models import PackageCategory, HostingPackage
from django.test import Client

print("Total Categories:", PackageCategory.objects.count())
for cat in PackageCategory.objects.all():
    print(f"  - {cat.name} ({cat.slug}) -> {cat.packages.count()} packages")

client = Client()
res = client.get('/')
print("Landing page status:", res.status_code)
print("selectCategoryTab in HTML:", b"selectCategoryTab" in res.content)
print("Domain &amp; Hosting OFFER in HTML:", b"Domain &amp; Hosting OFFER" in res.content)

# Test BDIX page
res_bdix = client.get('/hosting/bdix/')
print("BDIX page status:", res_bdix.status_code)
EOF
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()

