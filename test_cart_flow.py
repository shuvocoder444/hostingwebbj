import re
import requests
import json

BASE_URL = "https://host.webkoders.com"

def test_full_order_flow():
    session = requests.Session()
    
    # 1. Step 1: Load cart
    r1 = session.get(f"{BASE_URL}/cart/")
    print("Step 1 Cart Domain status:", r1.status_code)
    
    # 2. Check live domain search
    r_check = session.get(f"{BASE_URL}/api/v1/domains/ajax-check/?domain=myautotestlive&tld=.com")
    print("Live domain check:", r_check.status_code, r_check.json())
    
    # 3. Extract package id from cart HTML
    m = re.search(r'package=([0-9a-fA-F-]+)', r1.text)
    if m:
        package_id = m.group(1)
        print("Found Package ID:", package_id)
        
        r2 = session.get(f"{BASE_URL}/cart/configure/?package={package_id}&domain=myautotestlive.com&domain_option=register&tld=.com")
        print("Step 2 Configure status:", r2.status_code)
        
        r3 = session.get(f"{BASE_URL}/cart/checkout/?package={package_id}&domain=myautotestlive.com&domain_option=register&billing_cycle=annual&tld=.com")
        print("Step 3 Checkout status:", r3.status_code)
    else:
        print("Could not find package_id in cart response.")
    if package_id:
        r2 = session.get(f"{BASE_URL}/cart/configure/?package={package_id}&domain=myautotestlive.com&domain_option=register&tld=.com")
        print("Step 2 Configure status:", r2.status_code)
        
        r3 = session.get(f"{BASE_URL}/cart/checkout/?package={package_id}&domain=myautotestlive.com&domain_option=register&billing_cycle=annual&tld=.com")
        print("Step 3 Checkout status:", r3.status_code)

if __name__ == '__main__':
    test_full_order_flow()
