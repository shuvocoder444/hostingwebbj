import os, pprint, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()

from hosting.models import HostingAccount
from hosting.drivers.factory import get_driver

acc = HostingAccount.objects.filter(status='active').first()
driver = get_driver(acc.server)
print(f"Checking accountsummary for {acc.username} on {acc.server.name}:")

# 1. WHM accountsummary call
res = driver._call('accountsummary', params={'user': acc.username})
pprint.pprint(res)

# 2. Let's also check cPanel UAPI for quota and disk usage
# In cPanel UAPI: Quota::get_local_quota_info or Stats::get_site_stats or DiskUsage
from hosting.cpanel_uapi import CPanelUAPIManager
uapi = CPanelUAPIManager(acc)

print("\n--- Testing UAPI Quota::get_local_quota_info ---")
r_quota = uapi.call_uapi('Quota', 'get_local_quota_info')
pprint.pprint(r_quota)

print("\n--- Testing UAPI Stats::get_site_stats ---")
r_stats = uapi.call_uapi('Stats', 'get_site_stats')
pprint.pprint(r_stats)

