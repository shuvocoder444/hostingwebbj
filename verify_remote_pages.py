import requests
import sys

BASE_URL = "https://host.webkoders.com"

def test_endpoints():
    endpoints = [
        "/",
        "/cart/",
        "/login/",
        "/register/",
    ]
    
    print("Testing live endpoints on host.webkoders.com...")
    for ep in endpoints:
        url = BASE_URL + ep
        try:
            res = requests.get(url, timeout=15, verify=True)
            print(f"[{res.status_code}] {url}")
            if res.status_code >= 500:
                print(f"  -> ERROR 500 Detected on {url}!")
        except Exception as e:
            print(f"[FAIL] {url} - {e}")

if __name__ == '__main__':
    test_endpoints()
