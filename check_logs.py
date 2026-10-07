import paramiko
import sys

def check_remote():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    key = paramiko.RSAKey.from_private_key_file("C:/Users/shuvo/.ssh/id_rsa", password="SHUVOshuvo123@")
    ssh.connect("195.250.26.201", username="webkoders", pkey=key, port=22)
    
    commands = [
        "tail -n 60 /home/webkoders/host.webkoders.com/stderr.log",
        "tail -n 60 /home/webkoders/host.webkoders.com/passenger.log",
        "/home/webkoders/virtualenv/host.webkoders.com/3.12/bin/python /home/webkoders/host.webkoders.com/manage.py showmigrations"
    ]
    
    for cmd in commands:
        print(f"=== Running: {cmd} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        if out:
            print(f"[STDOUT]\n{out}")
        if err:
            print(f"[STDERR]\n{err}")

    ssh.close()

if __name__ == '__main__':
    check_remote()
