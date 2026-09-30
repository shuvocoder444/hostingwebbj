import requests
import re

s = requests.Session()
r1 = s.get('http://127.0.0.1:8000/login/')
csrf = s.cookies.get('csrftoken', '')
print('CSRF token from cookie:', csrf)

r2 = s.post(
    'http://127.0.0.1:8000/login/',
    data={
        'email': 'client@example.com',
        'password': 'HostPro@123',
        'csrfmiddlewaretoken': csrf,
    },
    headers={'Referer': 'http://127.0.0.1:8000/login/'}
)
print('r2 status:', r2.status_code, 'r2 history:', [h.status_code for h in r2.history], 'r2 url:', r2.url)
if 'flex-1 text-sm' in r2.text:
    print('Message from page:', r2.text.split('flex-1 text-sm font-medium leading-relaxed">')[1].split('</div>')[0])

r3 = s.get('http://127.0.0.1:8000/dashboard/')
print('r3 status:', r3.status_code)
print('Contains Tanvir in dashboard:', 'Tanvir' in r3.text)
print('Contains ahmedsolutions.com.bd:', 'ahmedsolutions.com.bd' in r3.text)
print('Contains INV-00001:', 'INV-00001' in r3.text)
