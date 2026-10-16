import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
ssh.connect('195.250.26.201', username='webkoders', pkey=key, port=22, timeout=30)

cmd = '''
/home/webkoders/virtualenv/velohoster.com/3.12/bin/python /home/webkoders/velohoster.com/manage.py shell << 'EOF'
import traceback
try:
    from django.test import RequestFactory
    from core.admin_views import admin_dashboard_view
    from accounts.models import User
    admin_u = User.objects.filter(is_superuser=True).first()
    rf = RequestFactory()
    req = rf.get('/admin-dashboard/')
    req.user = admin_u
    resp = admin_dashboard_view(req)
    print("ADMIN DASHBOARD STATUS:", resp.status_code)
except Exception:
    traceback.print_exc()
EOF
'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()
