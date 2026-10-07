import paramiko

def check_users():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
    ssh.connect('195.250.26.201', username='webkoders', pkey=key, port=22, timeout=30, banner_timeout=60)
    
    script = """
from django.contrib.auth import get_user_model
from hosting.models import HostingAccount
from billing.models import Invoice, Transaction
from domains.models import Domain

User = get_user_model()
print('=== USERS ===')
for u in User.objects.all():
    cb = getattr(getattr(u, 'profile', None), 'credit_balance', 0)
    print(f'User: {u.email} | Role: {u.role} | Active: {u.is_active} | Wallet: {cb}')

print('\\n=== HOSTING ACCOUNTS ===')
for a in HostingAccount.objects.all():
    print(f'Account: {a.domain} ({a.username}) | Status: {a.status} | User: {a.user.email}')

print('\\n=== INVOICES ===')
for inv in Invoice.objects.all():
    print(f'Invoice: #{inv.invoice_number} | Status: {inv.status} | Total: {inv.total} | User: {inv.user.email}')
"""
    
    cmd = f"/home/webkoders/virtualenv/host.webkoders.com/3.12/bin/python /home/webkoders/host.webkoders.com/manage.py shell -c \"{script}\""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
    print("OUTPUT:\n", out)
    if err:
        print("STDERR:\n", err)
    ssh.close()

if __name__ == '__main__':
    check_users()
