import os

import paramiko

FILES_TO_UPLOAD = [
    'templates/base.html',
    'templates/index.html',
    'templates/cart_domain.html',
    'templates/cart_checkout.html',
    'templates/cart_configure.html',
    'templates/register.html',
    'templates/login.html',
    'templates/dashboard.html',
    'templates/service_detail.html',
    'templates/admin_dashboard.html',
    'templates/partials/brand_logo.html',
    'templates/pages/about_us.html',
    'templates/pages/contact_us.html',
    'templates/pages/our_datacenter.html',
    'templates/pages/blog.html',
    'templates/pages/domain_register.html',
    'templates/pages/domain_transfer.html',
    'templates/pages/hosting_singapore.html',
    'templates/pages/hosting_usa.html',
    'templates/pages/hosting_bdix.html',
    'templates/pages/hosting_premium.html',
    'templates/pages/hosting_turbo_cloud.html',
    'templates/pages/hosting_reseller.html',
    'templates/pages/hosting_vps.html',
    'hostpro/settings.py',
    'hostpro/urls.py',
    'core/models.py',
    'core/page_views.py',
    'core/migrations/__init__.py',
    'core/migrations/0001_initial.py',
    'core/migrations/0002_alter_sitesetting_company_name_and_more.py',
    'core/migrations/0003_sitesetting_show_hero_section.py',
    'core/migrations/0004_sitesetting_binance_pay_id_and_more.py',
    'billing/urls.py',
    'domains/migrations/0002_alter_domainregistrar_driver.py',
    'core/context_processors.py',
    'core/signals.py',
    'core/cache.py',
    'core/sitemaps.py',
    'core/security.py',
    'hosting/services.py',
    'hosting/models.py',
    'hosting/views.py',
    'hosting/tasks.py',
    'accounts/models.py',
    'accounts/views.py',
    'accounts/serializers.py',
    'core/views.py',
    'core/admin_views.py',
    'core/cart_views.py',
    'domains/models.py',
    'domains/services.py',
    'domains/views.py',
    'domains/whois_checker.py',
    'domains/drivers/__init__.py',
    'domains/drivers/factory.py',
    'domains/drivers/spaceship.py',
    'domains/drivers/bdwebs.py',
    'billing/models.py',
    'billing/views.py',
    'billing/services.py',
    'billing/gateway_factory.py',
    'static/images/server-rack-hero.svg',
    'static/images/domain-cloud-hero.svg',
    'static/images/cpanel-mockup.svg',
    'static/images/speed-benchmark.svg',
    'static/images/datacenter-map.svg',
    'static/images/curved-world-map.svg',
    'static/images/os-almalinux.svg',
    'static/images/os-rockylinux.svg',
    'static/images/os-ubuntu.svg',
    'static/images/os-webuzo-alma.svg',
    'static/images/os-webuzo-ubuntu.svg',
    'static/images/migration-transfer.svg',
    'static/images/vps-architecture.svg',
    'static/images/reseller-whm.svg',
    'static/images/banner-3.gif',
    'static/images/banner-3.webp',
    'static/img/logo.png',
    'static/img/favicon.png',
    'static/img/favicon.ico',
    'static/img/og_thumbnail.png',
]

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
        
        # Ensure directories exist
        for d in ['templates/partials', 'templates/pages', 'core/migrations', 'domains/migrations', 'hosting/migrations', 'static/images', 'staticfiles/images', 'static/img', 'staticfiles/img', 'mediafiles', 'tmp']:
            run_cmd(ssh, f"mkdir -p {base_dir}/{d}")
        
        for rel_path in FILES_TO_UPLOAD:
            if os.path.exists(rel_path):
                remote_file = f"{base_dir}/{rel_path}"
                sftp.put(rel_path, remote_file)
                print(f"  Uploaded: {rel_path}", flush=True)
                
        py_bin = "/home/webkoders/virtualenv/host.webkoders.com/3.12/bin/python"
        
        # Run migrations
        run_cmd(ssh, f"{py_bin} {base_dir}/manage.py migrate")
        
        # Update SiteSetting in DB to VeloHoster using python remote script
        update_py = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()
from core.models import SiteSetting
from django.core.cache import cache

for s in SiteSetting.objects.all():
    s.company_name = 'VeloHoster'
    if 'HostPro' in s.site_title:
        s.site_title = s.site_title.replace('HostPro', 'VeloHoster')
    if s.support_email == 'support@webkoders.com':
        s.support_email = 'support@velohoster.com'
    s.save()
cache.clear()
print('SUCCESS: Updated SiteSetting to VeloHoster in database.')
"""
        with sftp.open(f"{base_dir}/update_branding_db.py", "w") as f:
            f.write(update_py)
            
        code, out, err = run_cmd(ssh, f"cd {base_dir} && {py_bin} update_branding_db.py")
        print(f"  [{base_dir}] DB Result: {out.strip()} {err.strip()}", flush=True)
        run_cmd(ssh, f"rm -f {base_dir}/update_branding_db.py")
        
        # Collect static
        run_cmd(ssh, f"{py_bin} {base_dir}/manage.py collectstatic --noinput")
        
        # Restart Passenger
        run_cmd(ssh, f"touch {base_dir}/tmp/restart.txt")
        print(f"[OK] {base_dir} updated and restarted.", flush=True)
        
    sftp.close()
    ssh.close()
    print("\nDeployment completed successfully to all target environments!", flush=True)

if __name__ == '__main__':
    deploy()
