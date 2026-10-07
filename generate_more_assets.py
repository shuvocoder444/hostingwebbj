import os

os.makedirs('d:/hosting/static/images', exist_ok=True)

# 1. Migration Transfer Graphic
migration_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 320" fill="none" class="w-full h-auto">
  <defs>
    <linearGradient id="migGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#059669" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0.1"/>
    </linearGradient>
  </defs>

  <rect width="540" height="320" rx="20" fill="#0f172a" stroke="#1e293b" stroke-width="2"/>

  <!-- Left Side: Old Slow Server -->
  <g transform="translate(40, 70)">
    <rect width="160" height="180" rx="16" fill="#1e293b" stroke="#475569" stroke-width="1.5"/>
    <rect x="20" y="20" width="120" height="24" rx="6" fill="#334155"/>
    <text x="35" y="36" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">OLD PROVIDER</text>
    
    <circle cx="35" cy="75" r="5" fill="#ef4444"/>
    <text x="50" y="78" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="10">Slow Load Times</text>
    
    <circle cx="35" cy="105" r="5" fill="#f59e0b"/>
    <text x="50" y="108" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="10">High Downtime</text>

    <circle cx="35" cy="135" r="5" fill="#64748b"/>
    <text x="50" y="138" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="10">Poor Support</text>
  </g>

  <!-- Middle Arrow & Zero Downtime Badge -->
  <g transform="translate(215, 120)">
    <path d="M10 40 L90 40 M70 20 L90 40 L70 60" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    <rect x="-10" y="70" width="130" height="34" rx="10" fill="#064e3b" stroke="#10b981" stroke-width="1.5"/>
    <text x="0" y="91" fill="#34d399" font-family="system-ui, sans-serif" font-size="10" font-weight="900">ZERO DOWNTIME</text>
  </g>

  <!-- Right Side: VeloHoster High Speed Cloud -->
  <g transform="translate(340, 70)">
    <rect width="160" height="180" rx="16" fill="#132338" stroke="#0284c7" stroke-width="2"/>
    <rect x="20" y="20" width="120" height="24" rx="6" fill="#0369a1"/>
    <text x="32" y="36" fill="#ffffff" font-family="system-ui, sans-serif" font-size="10" font-weight="900">VELOHOSTER</text>
    
    <circle cx="35" cy="75" r="5" fill="#10b981"/>
    <text x="50" y="78" fill="#ffffff" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">NVMe 7,000 MB/s</text>
    
    <circle cx="35" cy="105" r="5" fill="#38bdf8"/>
    <text x="50" y="108" fill="#ffffff" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">LiteSpeed 6X Fast</text>

    <circle cx="35" cy="135" r="5" fill="#10b981"/>
    <text x="50" y="138" fill="#34d399" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">100% Free Transfer</text>
  </g>
</svg>
"""

# 2. Cloud VPS KVM Architecture
vps_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 320" fill="none" class="w-full h-auto">
  <rect width="540" height="320" rx="20" fill="#090d16" stroke="#1e293b" stroke-width="2"/>

  <!-- Physical Node Base -->
  <rect x="40" y="220" width="460" height="70" rx="12" fill="#111827" stroke="#374151" stroke-width="1.5"/>
  <text x="60" y="250" fill="#f8fafc" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">Bare Metal Enterprise Node (AMD EPYC 9654 / DDR5 ECC)</text>
  <text x="60" y="270" fill="#38bdf8" font-family="monospace" font-size="10">KVM Hypervisor Isolation Pool • 100Gbps Redundant Network</text>

  <!-- VPS Slices on top -->
  <!-- VPS Instance 1 -->
  <g transform="translate(40, 40)">
    <rect width="140" height="160" rx="14" fill="#1e1b4b" stroke="#6366f1" stroke-width="2"/>
    <rect x="15" y="15" width="110" height="24" rx="6" fill="#312e81"/>
    <text x="32" y="31" fill="#c7d2fe" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">VPS Node 01</text>
    <text x="20" y="65" fill="#818cf8" font-family="system-ui, sans-serif" font-size="9">Dedicated 4 vCPU</text>
    <text x="20" y="85" fill="#818cf8" font-family="system-ui, sans-serif" font-size="9">8 GB DDR5 RAM</text>
    <text x="20" y="105" fill="#818cf8" font-family="system-ui, sans-serif" font-size="9">100 GB NVMe Disk</text>
    <rect x="15" y="125" width="110" height="20" rx="4" fill="#4338ca"/>
    <text x="35" y="139" fill="#ffffff" font-family="monospace" font-size="9">Root Access</text>
  </g>

  <!-- VPS Instance 2 -->
  <g transform="translate(200, 40)">
    <rect width="140" height="160" rx="14" fill="#042f2e" stroke="#14b8a6" stroke-width="2"/>
    <rect x="15" y="15" width="110" height="24" rx="6" fill="#115e59"/>
    <text x="32" y="31" fill="#ccfbf1" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">VPS Node 02</text>
    <text x="20" y="65" fill="#2dd4bf" font-family="system-ui, sans-serif" font-size="9">Dedicated 8 vCPU</text>
    <text x="20" y="85" fill="#2dd4bf" font-family="system-ui, sans-serif" font-size="9">16 GB DDR5 RAM</text>
    <text x="20" y="105" fill="#2dd4bf" font-family="system-ui, sans-serif" font-size="9">200 GB NVMe Disk</text>
    <rect x="15" y="125" width="110" height="20" rx="4" fill="#0d9488"/>
    <text x="35" y="139" fill="#ffffff" font-family="monospace" font-size="9">Root Access</text>
  </g>

  <!-- VPS Instance 3 -->
  <g transform="translate(360, 40)">
    <rect width="140" height="160" rx="14" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="15" y="15" width="110" height="24" rx="6" fill="#0369a1"/>
    <text x="32" y="31" fill="#e0f2fe" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">VPS Node 03</text>
    <text x="20" y="65" fill="#7dd3fc" font-family="system-ui, sans-serif" font-size="9">Dedicated 2 vCPU</text>
    <text x="20" y="85" fill="#7dd3fc" font-family="system-ui, sans-serif" font-size="9">4 GB DDR5 RAM</text>
    <text x="20" y="105" fill="#7dd3fc" font-family="system-ui, sans-serif" font-size="9">50 GB NVMe Disk</text>
    <rect x="15" y="125" width="110" height="20" rx="4" fill="#0284c7"/>
    <text x="35" y="139" fill="#ffffff" font-family="monospace" font-size="9">Root Access</text>
  </g>
</svg>
"""

# 3. Reseller WHM Cloud Ecosystem
reseller_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 320" fill="none" class="w-full h-auto">
  <rect width="540" height="320" rx="20" fill="#0f172a" stroke="#1e293b" stroke-width="2"/>

  <!-- Master Reseller WHM Account -->
  <g transform="translate(180, 30)">
    <rect width="180" height="80" rx="16" fill="#1e1b4b" stroke="#818cf8" stroke-width="2"/>
    <circle cx="35" cy="40" r="16" fill="#4f46e5"/>
    <text x="28" y="45" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12" font-weight="bold">👑</text>
    <text x="65" y="35" fill="#ffffff" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">WHM Control</text>
    <text x="65" y="52" fill="#a5b4fc" font-family="system-ui, sans-serif" font-size="9">100% White Label</text>
    <text x="65" y="66" fill="#34d399" font-family="system-ui, sans-serif" font-size="8">Custom DNS &amp; NS</text>
  </g>

  <!-- Connective Lines -->
  <path d="M270 110 L100 170 M270 110 L270 170 M270 110 L440 170" stroke="#6366f1" stroke-width="2" stroke-dasharray="4 3"/>

  <!-- Child Client cPanel 1 -->
  <g transform="translate(30, 170)">
    <rect width="140" height="110" rx="12" fill="#1e293b" stroke="#334155" stroke-width="1.5"/>
    <text x="18" y="30" fill="#f8fafc" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Client Store</text>
    <text x="18" y="50" fill="#94a3b8" font-family="monospace" font-size="9">client1.com</text>
    <rect x="18" y="65" width="104" height="6" rx="3" fill="#334155"/>
    <rect x="18" y="65" width="60" height="6" rx="3" fill="#3b82f6"/>
    <text x="18" y="90" fill="#38bdf8" font-family="system-ui, sans-serif" font-size="9">cPanel Package 1</text>
  </g>

  <!-- Child Client cPanel 2 -->
  <g transform="translate(200, 170)">
    <rect width="140" height="110" rx="12" fill="#1e293b" stroke="#334155" stroke-width="1.5"/>
    <text x="18" y="30" fill="#f8fafc" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Agency Client</text>
    <text x="18" y="50" fill="#94a3b8" font-family="monospace" font-size="9">client2.net</text>
    <rect x="18" y="65" width="104" height="6" rx="3" fill="#334155"/>
    <rect x="18" y="65" width="85" height="6" rx="3" fill="#10b981"/>
    <text x="18" y="90" fill="#34d399" font-family="system-ui, sans-serif" font-size="9">cPanel Package 2</text>
  </g>

  <!-- Child Client cPanel 3 -->
  <g transform="translate(370, 170)">
    <rect width="140" height="110" rx="12" fill="#1e293b" stroke="#334155" stroke-width="1.5"/>
    <text x="18" y="30" fill="#f8fafc" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Dev Portal</text>
    <text x="18" y="50" fill="#94a3b8" font-family="monospace" font-size="9">client3.org</text>
    <rect x="18" y="65" width="104" height="6" rx="3" fill="#334155"/>
    <rect x="18" y="65" width="40" height="6" rx="3" fill="#f59e0b"/>
    <text x="18" y="90" fill="#fbbf24" font-family="system-ui, sans-serif" font-size="9">cPanel Package 3</text>
  </g>
</svg>
"""

# Write all assets to disk
assets = {
    'd:/hosting/static/images/migration-transfer.svg': migration_svg,
    'd:/hosting/static/images/vps-architecture.svg': vps_svg,
    'd:/hosting/static/images/reseller-whm.svg': reseller_svg,
}

for filepath, content in assets.items():
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content.strip())
    print(f"Generated: {filepath}")
