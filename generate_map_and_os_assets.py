import os

os.makedirs('d:/hosting/static/images', exist_ok=True)

# 1. AlmaLinux SVG Logo
almalinux_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none" class="w-16 h-16">
  <g transform="translate(10, 10)">
    <circle cx="50" cy="50" r="48" fill="#10b981" fill-opacity="0.1"/>
    <!-- Interlocking people shape in emerald/green -->
    <path d="M50 15 C44 15 40 19 40 25 C40 31 44 35 50 35 C56 35 60 31 60 25 C60 19 56 15 50 15 Z" fill="#10b981"/>
    <path d="M25 40 C19 40 15 44 15 50 C15 56 19 60 25 60 C31 60 35 56 35 50 C35 44 31 40 25 40 Z" fill="#059669"/>
    <path d="M75 40 C69 40 65 44 65 50 C65 56 69 60 75 60 C81 60 85 56 85 50 C85 44 81 40 75 40 Z" fill="#34d399"/>
    <path d="M50 65 C44 65 40 69 40 75 C40 81 44 85 50 85 C56 85 60 81 60 75 C60 69 56 65 50 65 Z" fill="#047857"/>
    <path d="M35 32 Q 50 42 65 32 Q 68 48 78 50 Q 68 62 65 78 Q 50 68 35 78 Q 32 62 22 50 Q 32 48 35 32 Z" fill="#10b981" fill-opacity="0.85"/>
  </g>
</svg>
"""

# 2. Rocky Linux SVG Logo
rockylinux_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none" class="w-16 h-16">
  <circle cx="60" cy="60" r="48" fill="#ef4444" fill-opacity="0.08"/>
  <circle cx="60" cy="60" r="40" fill="#e11d48"/>
  <!-- Rocky mountain geometric cutout -->
  <path d="M60 32 L84 68 L70 68 L60 52 L50 68 L36 68 Z" fill="#ffffff"/>
  <path d="M60 62 L72 80 L48 80 Z" fill="#ffffff" fill-opacity="0.9"/>
</svg>
"""

# 3. Ubuntu SVG Logo
ubuntu_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none" class="w-16 h-16">
  <circle cx="60" cy="60" r="48" fill="#ea580c" fill-opacity="0.08"/>
  <!-- Ubuntu Circle of Friends in vibrant Orange -->
  <circle cx="60" cy="60" r="38" fill="#ea580c"/>
  <circle cx="60" cy="60" r="23" fill="#ffffff"/>
  <circle cx="60" cy="60" r="17" fill="#ea580c"/>
  
  <!-- 3 white heads and gaps -->
  <circle cx="28" cy="60" r="6" fill="#ea580c" stroke="#ffffff" stroke-width="3"/>
  <circle cx="76" cy="32" r="6" fill="#ea580c" stroke="#ffffff" stroke-width="3"/>
  <circle cx="76" cy="88" r="6" fill="#ea580c" stroke="#ffffff" stroke-width="3"/>

  <!-- Segment Cuts -->
  <rect x="20" y="58" width="22" height="4" fill="#ffffff"/>
  <line x1="60" y1="60" x2="78" y2="30" stroke="#ffffff" stroke-width="4"/>
  <line x1="60" y1="60" x2="78" y2="90" stroke="#ffffff" stroke-width="4"/>
</svg>
"""

# 4. Webuzo AlmaLinux 9.8 Logo
webuzo_alma_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none" class="w-16 h-16">
  <circle cx="60" cy="60" r="48" fill="#0284c7" fill-opacity="0.08"/>
  <!-- Webuzo Multi-Color Ring & 'we' emblem -->
  <circle cx="60" cy="60" r="38" fill="none" stroke="url(#webuzoGrad)" stroke-width="8"/>
  <defs>
    <linearGradient id="webuzoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ef4444"/>
      <stop offset="33%" stop-color="#f59e0b"/>
      <stop offset="66%" stop-color="#10b981"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>
  </defs>
  <text x="32" y="68" fill="#0284c7" font-family="system-ui, sans-serif" font-size="22" font-weight="900">we</text>
</svg>
"""

# 5. Webuzo Ubuntu 24.04 Logo
webuzo_ubuntu_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" fill="none" class="w-16 h-16">
  <circle cx="60" cy="60" r="48" fill="#ea580c" fill-opacity="0.08"/>
  <!-- Crown on Webuzo/Ubuntu Circle -->
  <path d="M42 34 L48 24 L60 30 L72 24 L78 34 Z" fill="#f59e0b" stroke="#d97706" stroke-width="1.5"/>
  <circle cx="60" cy="65" r="32" fill="#0284c7"/>
  <circle cx="60" cy="65" r="18" fill="#ffffff"/>
  <!-- Ubuntu orange & webuzo elements inside -->
  <circle cx="60" cy="65" r="12" fill="#ea580c"/>
  <circle cx="44" cy="65" r="4" fill="#ffffff"/>
  <circle cx="70" cy="50" r="4" fill="#ffffff"/>
  <circle cx="70" cy="80" r="4" fill="#ffffff"/>
</svg>
"""

assets = {
    'd:/hosting/static/images/os-almalinux.svg': almalinux_svg,
    'd:/hosting/static/images/os-rockylinux.svg': rockylinux_svg,
    'd:/hosting/static/images/os-ubuntu.svg': ubuntu_svg,
    'd:/hosting/static/images/os-webuzo-alma.svg': webuzo_alma_svg,
    'd:/hosting/static/images/os-webuzo-ubuntu.svg': webuzo_ubuntu_svg,
}

for filepath, content in assets.items():
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content.strip())
    print(f"Generated: {filepath}")
