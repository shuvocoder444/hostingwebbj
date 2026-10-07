import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hostpro.settings')
django.setup()

from django.template.loader import get_template
from pathlib import Path

template_dir = Path(settings.BASE_DIR) / 'templates'
errors = []

for template_path in template_dir.rglob('*.html'):
    rel_path = template_path.relative_to(template_dir)
    try:
        get_template(str(rel_path).replace('\\', '/'))
        print(f"[OK] {rel_path}")
    except Exception as e:
        print(f"[ERROR] {rel_path}: {e}")
        errors.append((rel_path, str(e)))

print("\n--- Summary ---")
if errors:
    print(f"Found {len(errors)} template errors:")
    for path, err in errors:
        print(f"  {path}: {err}")
else:
    print("All templates compiled successfully!")
