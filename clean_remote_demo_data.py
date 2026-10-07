import paramiko

def clean_demo_data():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
    ssh.connect('195.250.26.201', username='webkoders', pkey=key, port=22)
    
    script = """
from django.contrib.auth import get_user_model
from accounts.models import ClientProfile
from decimal import Decimal

User = get_user_model()

# 1. Remove demo admin user if exists
demo_admins = User.objects.filter(email='admin@hostpro.com')
for da in demo_admins:
    print('Deleting demo admin:', da.email)
    da.delete()

# 2. Reset any leftover 100 bonus wallet credits to 0.00 for clean live production
profiles = ClientProfile.objects.filter(credit_balance__gt=0)
for p in profiles:
    print('Resetting wallet for', p.user.email, 'from', p.credit_balance, 'to 0.00')
    p.credit_balance = Decimal('0.00')
    p.save(update_fields=['credit_balance'])

print('SUCCESS: Demo accounts and balances cleaned!')
"""
    
    stdin, stdout, stderr = ssh.exec_command("/home/webkoders/virtualenv/host.webkoders.com/3.12/bin/python /home/webkoders/host.webkoders.com/manage.py shell")
    stdin.write(script)
    stdin.flush()
    stdin.channel.shutdown_write()
    
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    print("OUTPUT:\n", out)
    if err:
        print("STDERR:\n", err)
    ssh.close()

if __name__ == '__main__':
    clean_demo_data()
