import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
ssh.connect('195.250.26.201', username='webkoders', pkey=key, port=22, timeout=45)

cmd = """cd /home/webkoders/velohoster.com && /home/webkoders/virtualenv/velohoster.com/3.12/bin/python - << 'EOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()
from hosting.models import HostingPackage, PackageCategory
for p in HostingPackage.objects.all():
    print(f"Name: {p.name} | Cat: {p.category.name if p.category else None} ({p.category.slug if p.category else None}) | TargetPage: {p.target_page} | Monthly: {p.monthly_price} | Annual: {p.annual_price}")
EOF
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()

