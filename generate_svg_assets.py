import os

os.makedirs('d:/hosting/static/images', exist_ok=True)

# 1. Hero Server Rack Illustration
hero_server_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 420" fill="none" class="w-full h-auto">
  <defs>
    <linearGradient id="srvGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e1e2f"/>
      <stop offset="100%" stop-color="#0d0d15"/>
    </linearGradient>
    <linearGradient id="neonBlue" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="50%" stop-color="#6366f1"/>
      <stop offset="100%" stop-color="#a855f7"/>
    </linearGradient>
    <linearGradient id="nvmeGlow" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#10b981"/>
      <stop offset="100%" stop-color="#06b6d4"/>
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Ambient Glow -->
  <circle cx="300" cy="210" r="180" fill="#4f46e5" opacity="0.15" filter="url(#glow)"/>

  <!-- Server Rack Frame -->
  <rect x="120" y="30" width="360" height="360" rx="24" fill="url(#srvGrad1)" stroke="#334155" stroke-width="2"/>
  
  <!-- Server Unit 1: Top Blade (Master Controller) -->
  <g transform="translate(140, 50)">
    <rect x="0" y="0" width="320" height="70" rx="12" fill="#151722" stroke="#25293c" stroke-width="1.5"/>
    <!-- Drive Bays -->
    <rect x="16" y="16" width="38" height="38" rx="6" fill="#1e2235" stroke="#374151" stroke-width="1"/>
    <rect x="62" y="16" width="38" height="38" rx="6" fill="#1e2235" stroke="#374151" stroke-width="1"/>
    <rect x="108" y="16" width="38" height="38" rx="6" fill="#1e2235" stroke="#374151" stroke-width="1"/>
    <rect x="154" y="16" width="38" height="38" rx="6" fill="#1e2235" stroke="#374151" stroke-width="1"/>
    <!-- LED Indicators -->
    <circle cx="210" cy="35" r="4" fill="#10b981" filter="url(#glow)"/>
    <circle cx="226" cy="35" r="4" fill="#3b82f6" filter="url(#glow)"/>
    <circle cx="242" cy="35" r="4" fill="#10b981"/>
    <!-- Unit Label -->
    <text x="265" y="32" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="9" font-weight="700">AMD EPYC</text>
    <text x="265" y="44" fill="#38bdf8" font-family="system-ui, sans-serif" font-size="8" font-weight="600">64 CORES</text>
  </g>

  <!-- Server Unit 2: Middle Blade (Enterprise NVMe Gen4 Storage Pool) -->
  <g transform="translate(140, 130)">
    <rect x="0" y="0" width="320" height="70" rx="12" fill="#151722" stroke="#4f46e5" stroke-width="1.5" stroke-dasharray="4 2"/>
    <!-- NVMe Heat Syncs -->
    <rect x="16" y="14" width="70" height="42" rx="8" fill="url(#nvmeGlow)" opacity="0.12" stroke="#10b981" stroke-width="1.5"/>
    <text x="28" y="32" fill="#34d399" font-family="monospace" font-size="9" font-weight="bold">NVMe 4.0</text>
    <text x="28" y="45" fill="#6ee7b7" font-family="monospace" font-size="8">7000 MB/s</text>

    <!-- Real-time Activity Meter -->
    <rect x="96" y="20" width="130" height="6" rx="3" fill="#1e293b"/>
    <rect x="96" y="20" width="105" height="6" rx="3" fill="url(#neonBlue)"/>
    <rect x="96" y="34" width="130" height="6" rx="3" fill="#1e293b"/>
    <rect x="96" y="34" width="75" height="6" rx="3" fill="#10b981"/>
    <text x="96" y="52" fill="#64748b" font-family="system-ui, sans-serif" font-size="8">I/O THROUGHPUT: 99.8%</text>

    <!-- Status -->
    <rect x="238" y="22" width="68" height="26" rx="6" fill="#10b981" fill-opacity="0.15" stroke="#10b981" stroke-width="1"/>
    <text x="250" y="38" fill="#34d399" font-family="system-ui, sans-serif" font-size="9" font-weight="bold">ONLINE</text>
  </g>

  <!-- Server Unit 3: LiteSpeed Web Server Engine -->
  <g transform="translate(140, 210)">
    <rect x="0" y="0" width="320" height="70" rx="12" fill="#151722" stroke="#25293c" stroke-width="1.5"/>
    <!-- LiteSpeed Logo Concept -->
    <circle cx="36" cy="35" r="18" fill="#4f46e5" fill-opacity="0.2" stroke="#6366f1" stroke-width="1.5"/>
    <path d="M36 24 L28 36 L34 36 L32 46 L44 33 L38 33 Z" fill="#38bdf8"/>
    
    <text x="64" y="32" fill="#ffffff" font-family="system-ui, sans-serif" font-size="11" font-weight="800">LiteSpeed Enterprise</text>
    <text x="64" y="46" fill="#818cf8" font-family="system-ui, sans-serif" font-size="9">HTTP/3 + QUIC + LSCache Active</text>

    <circle cx="280" cy="35" r="5" fill="#10b981" filter="url(#glow)"/>
    <circle cx="295" cy="35" r="5" fill="#38bdf8" filter="url(#glow)"/>
  </g>

  <!-- Server Unit 4: 10Gbps BDIX & Global Optical Switch -->
  <g transform="translate(140, 290)">
    <rect x="0" y="0" width="320" height="70" rx="12" fill="#151722" stroke="#25293c" stroke-width="1.5"/>
    <!-- Optical Ports -->
    <rect x="16" y="20" width="16" height="12" rx="2" fill="#0f172a" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="36" y="20" width="16" height="12" rx="2" fill="#0f172a" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="56" y="20" width="16" height="12" rx="2" fill="#0f172a" stroke="#10b981" stroke-width="1.5"/>
    <rect x="76" y="20" width="16" height="12" rx="2" fill="#0f172a" stroke="#10b981" stroke-width="1.5"/>
    <rect x="96" y="20" width="16" height="12" rx="2" fill="#0f172a" stroke="#6366f1" stroke-width="1.5"/>

    <text x="16" y="52" fill="#34d399" font-family="monospace" font-size="9" font-weight="bold">&lt; 5ms BDIX</text>
    <text x="86" y="52" fill="#94a3b8" font-family="monospace" font-size="9">10Gbps UPLINK</text>

    <!-- Shield / DDoS indicator -->
    <rect x="220" y="20" width="86" height="30" rx="8" fill="#1e1b4b" stroke="#6366f1" stroke-width="1"/>
    <text x="232" y="38" fill="#a5b4fc" font-family="system-ui, sans-serif" font-size="8" font-weight="bold">DDOS SHIELD</text>
  </g>

  <!-- Floating Stats Badges -->
  <g transform="translate(40, 160)">
    <rect width="110" height="46" rx="12" fill="#0f172a" stroke="#3b82f6" stroke-width="1.5" filter="url(#glow)"/>
    <text x="12" y="20" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="8" font-weight="600">UPTIME SLA</text>
    <text x="12" y="36" fill="#38bdf8" font-family="system-ui, sans-serif" font-size="14" font-weight="900">99.99%</text>
  </g>

  <g transform="translate(450, 240)">
    <rect width="110" height="46" rx="12" fill="#0f172a" stroke="#10b981" stroke-width="1.5" filter="url(#glow)"/>
    <text x="12" y="20" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="8" font-weight="600">PROVISION TIME</text>
    <text x="12" y="36" fill="#34d399" font-family="system-ui, sans-serif" font-size="14" font-weight="900">&lt; 15 SEC</text>
  </g>
</svg>
"""

# 2. Domain & Cloud Search Graphic
domain_hero_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 380" fill="none" class="w-full h-auto">
  <defs>
    <linearGradient id="globeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#4f46e5" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#06b6d4" stop-opacity="0.05"/>
    </linearGradient>
    <linearGradient id="chipGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="100%" stop-color="#a855f7"/>
    </linearGradient>
    <filter id="badgeGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Central Orbital Grid Globe -->
  <circle cx="250" cy="190" r="130" fill="url(#globeGrad)" stroke="#4338ca" stroke-width="1.5" stroke-dasharray="4 3"/>
  <ellipse cx="250" cy="190" rx="130" ry="45" fill="none" stroke="#6366f1" stroke-width="1" opacity="0.6"/>
  <ellipse cx="250" cy="190" rx="45" ry="130" fill="none" stroke="#6366f1" stroke-width="1" opacity="0.6"/>
  
  <!-- Central Search Core -->
  <circle cx="250" cy="190" r="45" fill="#0f172a" stroke="#818cf8" stroke-width="2"/>
  <path d="M242 182 A10 10 0 1 0 256 196 L264 204" stroke="#38bdf8" stroke-width="3" stroke-linecap="round"/>

  <!-- Floating TLD Badges with Shadows -->
  <!-- .COM -->
  <g transform="translate(60, 90)">
    <rect width="90" height="40" rx="12" fill="#1e1b4b" stroke="#818cf8" stroke-width="1.5"/>
    <circle cx="20" cy="20" r="6" fill="#10b981"/>
    <text x="34" y="24" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="800">.COM</text>
  </g>

  <!-- .NET -->
  <g transform="translate(350, 70)">
    <rect width="90" height="40" rx="12" fill="#1e1b4b" stroke="#c084fc" stroke-width="1.5"/>
    <circle cx="20" cy="20" r="6" fill="#a855f7"/>
    <text x="34" y="24" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="800">.NET</text>
  </g>

  <!-- .BD ccTLD -->
  <g transform="translate(40, 240)">
    <rect width="110" height="44" rx="12" fill="#064e3b" stroke="#34d399" stroke-width="2" filter="url(#badgeGlow)"/>
    <circle cx="24" cy="22" r="7" fill="#ef4444"/>
    <text x="40" y="26" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="900">.COM.BD</text>
  </g>

  <!-- .ORG -->
  <g transform="translate(340, 260)">
    <rect width="90" height="40" rx="12" fill="#1e1b4b" stroke="#38bdf8" stroke-width="1.5"/>
    <circle cx="20" cy="20" r="6" fill="#0284c7"/>
    <text x="34" y="24" fill="#ffffff" font-family="system-ui, sans-serif" font-size="13" font-weight="800">.ORG</text>
  </g>

  <!-- .XYZ & .IO -->
  <g transform="translate(205, 30)">
    <rect width="90" height="36" rx="10" fill="#0f172a" stroke="#f59e0b" stroke-width="1.5"/>
    <text x="24" y="23" fill="#fbbf24" font-family="system-ui, sans-serif" font-size="12" font-weight="800">.XYZ</text>
  </g>

  <!-- DNS Lock Shield -->
  <g transform="translate(215, 310)">
    <rect width="70" height="28" rx="8" fill="#1e293b" stroke="#10b981" stroke-width="1"/>
    <text x="14" y="18" fill="#34d399" font-family="system-ui, sans-serif" font-size="9" font-weight="bold">FREE DNS</text>
  </g>
</svg>
"""

# 3. cPanel & Cloud Dashboard Mockup Illustration
cpanel_mockup_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 360" fill="none" class="w-full h-auto">
  <defs>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#181826"/>
      <stop offset="100%" stop-color="#0f0f18"/>
    </linearGradient>
    <linearGradient id="barBlue" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
  </defs>

  <!-- Window Container -->
  <rect width="560" height="360" rx="20" fill="url(#cardGrad)" stroke="#27273a" stroke-width="2"/>
  
  <!-- Window Header (Mac Style) -->
  <rect width="560" height="42" rx="20" fill="#12121d"/>
  <circle cx="24" cy="21" r="5" fill="#ef4444"/>
  <circle cx="40" cy="21" r="5" fill="#f59e0b"/>
  <circle cx="56" cy="21" r="5" fill="#10b981"/>
  
  <!-- URL address bar -->
  <rect x="90" y="10" width="380" height="22" rx="6" fill="#1e1e2d"/>
  <text x="105" y="25" fill="#94a3b8" font-family="monospace" font-size="10">https://cpanel.velohoster.com:2083 [SSL Secure]</text>

  <!-- Left Sidebar inside Mockup -->
  <rect x="18" y="58" width="130" height="284" rx="12" fill="#13131f"/>
  <text x="32" y="85" fill="#64748b" font-family="system-ui, sans-serif" font-size="9" font-weight="700">GENERAL INFO</text>
  <text x="32" y="108" fill="#e2e8f0" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Shared IP</text>
  <text x="32" y="122" fill="#38bdf8" font-family="monospace" font-size="9">195.250.26.201</text>
  
  <text x="32" y="150" fill="#e2e8f0" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">PHP Version</text>
  <text x="32" y="164" fill="#34d399" font-family="monospace" font-size="9">PHP 8.3 (ea-php83)</text>

  <text x="32" y="192" fill="#e2e8f0" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">MySQL Version</text>
  <text x="32" y="206" fill="#cbd5e1" font-family="monospace" font-size="9">MariaDB 10.11</text>

  <text x="32" y="234" fill="#e2e8f0" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">AutoSSL</text>
  <text x="32" y="248" fill="#10b981" font-family="system-ui, sans-serif" font-size="9" font-weight="bold">Active &amp; Renewed</text>

  <!-- Main cPanel App Icons Grid -->
  <g transform="translate(164, 58)">
    <!-- Section 1: Top Stats -->
    <rect width="378" height="74" rx="12" fill="#161624" stroke="#262638" stroke-width="1"/>
    <!-- Disk Usage Bar -->
    <text x="18" y="25" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">NVMe Disk Usage</text>
    <rect x="18" y="34" width="160" height="8" rx="4" fill="#252538"/>
    <rect x="18" y="34" width="45" height="8" rx="4" fill="url(#barBlue)"/>
    <text x="18" y="56" fill="#64748b" font-family="system-ui, sans-serif" font-size="9">2.1 GB / 20 GB (10%)</text>

    <!-- Bandwidth Bar -->
    <text x="200" y="25" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">Bandwidth</text>
    <rect x="200" y="34" width="160" height="8" rx="4" fill="#252538"/>
    <rect x="200" y="34" width="30" height="8" rx="4" fill="#10b981"/>
    <text x="200" y="56" fill="#64748b" font-family="system-ui, sans-serif" font-size="9">Unlimited Bandwidth</text>

    <!-- Section 2: 1-Click Installer Icons -->
    <text x="4" y="105" fill="#e2e8f0" font-family="system-ui, sans-serif" font-size="12" font-weight="800">Softaculous 1-Click Apps</text>
    
    <!-- WordPress -->
    <rect x="4" y="118" width="84" height="68" rx="10" fill="#1c1c2e" stroke="#2e2e46" stroke-width="1"/>
    <circle cx="46" cy="144" r="14" fill="#0073aa"/>
    <text x="40" y="150" fill="#ffffff" font-family="system-ui, sans-serif" font-size="14" font-weight="bold">W</text>
    <text x="19" y="174" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="9" font-weight="bold">WordPress</text>

    <!-- phpMyAdmin / MySQL -->
    <rect x="98" y="118" width="84" height="68" rx="10" fill="#1c1c2e" stroke="#2e2e46" stroke-width="1"/>
    <circle cx="140" cy="144" r="14" fill="#f59e0b"/>
    <text x="135" y="149" fill="#ffffff" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">SQL</text>
    <text x="110" y="174" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="9" font-weight="bold">phpMyAdmin</text>

    <!-- LiteSpeed Cache -->
    <rect x="192" y="118" width="84" height="68" rx="10" fill="#1c1c2e" stroke="#4f46e5" stroke-width="1.5"/>
    <circle cx="234" cy="144" r="14" fill="#4f46e5"/>
    <text x="228" y="149" fill="#38bdf8" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">⚡</text>
    <text x="207" y="174" fill="#818cf8" font-family="system-ui, sans-serif" font-size="9" font-weight="bold">LSCache</text>

    <!-- Node.js / Python -->
    <rect x="286" y="118" width="84" height="68" rx="10" fill="#1c1c2e" stroke="#2e2e46" stroke-width="1"/>
    <circle cx="328" cy="144" r="14" fill="#10b981"/>
    <text x="323" y="149" fill="#ffffff" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">JS</text>
    <text x="303" y="174" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="9" font-weight="bold">Node / Py</text>

    <!-- Section 3: File Manager & Emails -->
    <rect x="4" y="198" width="178" height="60" rx="10" fill="#1a1a2a" stroke="#2e2e46" stroke-width="1"/>
    <circle cx="30" cy="228" r="14" fill="#2563eb"/>
    <text x="25" y="233" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12">📁</text>
    <text x="54" y="222" fill="#ffffff" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">File Manager</text>
    <text x="54" y="238" fill="#64748b" font-family="system-ui, sans-serif" font-size="9">Direct Web FTP &amp; Git</text>

    <rect x="192" y="198" width="178" height="60" rx="10" fill="#1a1a2a" stroke="#2e2e46" stroke-width="1"/>
    <circle cx="218" cy="228" r="14" fill="#059669"/>
    <text x="213" y="233" fill="#ffffff" font-family="system-ui, sans-serif" font-size="12">✉️</text>
    <text x="242" y="222" fill="#ffffff" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">Email Accounts</text>
    <text x="242" y="238" fill="#64748b" font-family="system-ui, sans-serif" font-size="9">Webmail + SpamAssassin</text>
  </g>
</svg>
"""

# 4. LiteSpeed vs Traditional Hosting Speed Benchmark
speed_benchmark_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 260" fill="none" class="w-full h-auto">
  <rect width="540" height="260" rx="16" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
  
  <text x="24" y="36" fill="#f8fafc" font-family="system-ui, sans-serif" font-size="14" font-weight="bold">Page Load Response Time (TTFB Benchmark)</text>
  <text x="24" y="54" fill="#94a3b8" font-family="system-ui, sans-serif" font-size="10">Tested across 1,000 concurrent WordPress requests (Lower is better)</text>

  <!-- VeloHoster LiteSpeed Bar -->
  <g transform="translate(24, 76)">
    <text x="0" y="18" fill="#38bdf8" font-family="system-ui, sans-serif" font-size="11" font-weight="bold">VeloHoster LiteSpeed + NVMe Gen4</text>
    <text x="420" y="18" fill="#34d399" font-family="monospace" font-size="12" font-weight="bold">280 ms</text>
    <rect x="0" y="26" width="492" height="24" rx="6" fill="#1e293b"/>
    <rect x="0" y="26" width="120" height="24" rx="6" fill="#0284c7"/>
    <rect x="0" y="26" width="90" height="24" rx="6" fill="#38bdf8"/>
    <text x="12" y="42" fill="#032b43" font-family="system-ui, sans-serif" font-size="9" font-weight="bold">6X FASTER</text>
  </g>

  <!-- Standard Cloud Hosting -->
  <g transform="translate(24, 138)">
    <text x="0" y="18" fill="#cbd5e1" font-family="system-ui, sans-serif" font-size="11">Standard Nginx / SSD Hosting</text>
    <text x="420" y="18" fill="#fbbf24" font-family="monospace" font-size="11">820 ms</text>
    <rect x="0" y="26" width="492" height="20" rx="6" fill="#1e293b"/>
    <rect x="0" y="26" width="260" height="20" rx="6" fill="#d97706"/>
  </g>

  <!-- Traditional HDD Hosting -->
  <g transform="translate(24, 192)">
    <text x="0" y="16" fill="#64748b" font-family="system-ui, sans-serif" font-size="10">Traditional Apache HDD Shared Host</text>
    <text x="420" y="16" fill="#ef4444" font-family="monospace" font-size="10">1,940 ms</text>
    <rect x="0" y="22" width="492" height="16" rx="4" fill="#1e293b"/>
    <rect x="0" y="22" width="440" height="16" rx="4" fill="#dc2626" opacity="0.6"/>
  </g>
</svg>
"""

# 5. Global Datacenter Map & Low Latency Mesh
datacenter_map_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 360" fill="none" class="w-full h-auto">
  <defs>
    <radialGradient id="meshGrad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#1e1b4b" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#09090e" stop-opacity="1"/>
    </radialGradient>
    <filter id="nodeGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <rect width="700" height="360" rx="24" fill="url(#meshGrad)" stroke="#2e2a56" stroke-width="1.5"/>

  <!-- World Map Stylized Dots / Grid -->
  <!-- Europe Area -->
  <g opacity="0.3" fill="#6366f1">
    <circle cx="280" cy="110" r="3"/><circle cx="295" cy="105" r="3"/><circle cx="310" cy="115" r="3"/>
    <circle cx="285" cy="125" r="3"/><circle cx="300" cy="130" r="3"/><circle cx="320" cy="120" r="3"/>
    <circle cx="270" cy="140" r="3"/><circle cx="290" cy="145" r="3"/><circle cx="315" cy="135" r="3"/>
  </g>

  <!-- Asia Area -->
  <g opacity="0.3" fill="#38bdf8">
    <circle cx="470" cy="140" r="3"/><circle cx="490" cy="145" r="3"/><circle cx="510" cy="135" r="3"/>
    <circle cx="460" cy="160" r="3"/><circle cx="485" cy="170" r="3"/><circle cx="520" cy="165" r="3"/>
    <circle cx="475" cy="190" r="3"/><circle cx="505" cy="195" r="3"/><circle cx="530" cy="180" r="3"/>
  </g>

  <!-- Optical Fiber Connection Lines -->
  <!-- Germany to Singapore -->
  <path d="M300 120 Q 390 130 520 230" stroke="#6366f1" stroke-width="2" stroke-dasharray="6 4" opacity="0.7"/>
  <!-- Singapore to Dhaka -->
  <path d="M520 230 Q 490 200 480 175" stroke="#10b981" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Germany to Dhaka -->
  <path d="M300 120 Q 380 140 480 175" stroke="#38bdf8" stroke-width="2" stroke-dasharray="6 4" opacity="0.7"/>

  <!-- Datacenter 1: Germany & Finland (Nuremberg/Helsinki) -->
  <g transform="translate(300, 120)">
    <circle cx="0" cy="0" r="14" fill="#4f46e5" fill-opacity="0.25" filter="url(#nodeGlow)"/>
    <circle cx="0" cy="0" r="6" fill="#818cf8"/>
    <rect x="14" y="-22" width="130" height="42" rx="8" fill="#181829" stroke="#6366f1" stroke-width="1"/>
    <text x="24" y="-8" fill="#ffffff" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">Germany / Finland</text>
    <text x="24" y="8" fill="#a5b4fc" font-family="monospace" font-size="8">Tier III+ / GDPR Green</text>
  </g>

  <!-- Datacenter 2: Singapore (Equinix SG1) -->
  <g transform="translate(520, 230)">
    <circle cx="0" cy="0" r="16" fill="#3b82f6" fill-opacity="0.25" filter="url(#nodeGlow)"/>
    <circle cx="0" cy="0" r="7" fill="#38bdf8"/>
    <rect x="-140" y="-18" width="125" height="42" rx="8" fill="#181829" stroke="#38bdf8" stroke-width="1"/>
    <text x="-130" y="-4" fill="#ffffff" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">Singapore Equinix</text>
    <text x="-130" y="12" fill="#38bdf8" font-family="monospace" font-size="8">30ms South Asia Hub</text>
  </g>

  <!-- Datacenter 3: Bangladesh BDIX (Dhaka POP) -->
  <g transform="translate(480, 175)">
    <circle cx="0" cy="0" r="20" fill="#10b981" fill-opacity="0.35" filter="url(#nodeGlow)"/>
    <circle cx="0" cy="0" r="8" fill="#34d399"/>
    <rect x="16" y="-20" width="135" height="44" rx="8" fill="#064e3b" stroke="#34d399" stroke-width="1.5" filter="url(#nodeGlow)"/>
    <text x="26" y="-6" fill="#ffffff" font-family="system-ui, sans-serif" font-size="10" font-weight="bold">Dhaka BDIX Core</text>
    <text x="26" y="10" fill="#6ee7b7" font-family="monospace" font-size="9" font-weight="bold">&lt; 5ms National Ping</text>
  </g>
</svg>
"""

# Write all assets to disk
assets = {
    'd:/hosting/static/images/server-rack-hero.svg': hero_server_svg,
    'd:/hosting/static/images/domain-cloud-hero.svg': domain_hero_svg,
    'd:/hosting/static/images/cpanel-mockup.svg': cpanel_mockup_svg,
    'd:/hosting/static/images/speed-benchmark.svg': speed_benchmark_svg,
    'd:/hosting/static/images/datacenter-map.svg': datacenter_map_svg,
}

for filepath, content in assets.items():
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content.strip())
    print(f"Generated: {filepath}")
