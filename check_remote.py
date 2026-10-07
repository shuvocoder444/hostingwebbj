import paramiko

def check():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
    ssh.connect('195.250.26.201', username='webkoders', pkey=key, port=22)
    
    cmd = (
        "cd /home/webkoders/host.webkoders.com && "
        "/home/webkoders/virtualenv/host.webkoders.com/3.12/bin/python -c \""
        "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings'); "
        "import django; django.setup(); "
        "from domains.drivers.factory import get_registrar_driver; "
        "from domains.models import DomainRegistrar; "
        "r = DomainRegistrar.objects.filter(driver='spaceship').first(); "
        "d = get_registrar_driver(r) if r else None; "
        "print('Spaceship Registrar in DB:', r); "
        "print('Driver object:', d); "
        "print('Has list_domains:', hasattr(d, 'list_domains') if d else 'No driver');"
        "\""
    )
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print("STDOUT:", stdout.read().decode('utf-8'))
    print("STDERR:", stderr.read().decode('utf-8'))
    ssh.close()

if __name__ == '__main__':
    check()
