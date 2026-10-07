import os

# Create a clean curved 3D world projection SVG map
curved_map_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" fill="none" class="w-full h-auto">
  <defs>
    <linearGradient id="globeGradLight" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#f1f5f9" stop-opacity="0.95"/>
    </linearGradient>
    <radialGradient id="auraLeft" cx="15%" cy="30%" r="40%">
      <stop offset="0%" stop-color="#10b981" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="auraRight" cx="85%" cy="30%" r="40%">
      <stop offset="0%" stop-color="#ef4444" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <!-- Ambient Color Auras (Green on left, Pink/Red on right) -->
  <rect width="1200" height="600" fill="url(#auraLeft)"/>
  <rect width="1200" height="600" fill="url(#auraRight)"/>

  <!-- Curved Globe Outline / Meridian Arc -->
  <path d="M 50 380 Q 600 160 1150 440" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="6 4" opacity="0.4"/>
  <path d="M 100 480 Q 600 240 1100 520" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="4 4" opacity="0.3"/>

  <!-- Continents Vector Shapes (Curved Earth Projection in Dark Slate #1e293b / #2c3e50) -->
  <g fill="#27384e" opacity="0.92">
    <!-- North America (Curved west) -->
    <path d="M 120 320 Q 150 260 210 230 Q 260 210 320 225 Q 350 240 340 270 Q 300 280 270 300 Q 240 330 200 370 Q 160 380 130 350 Z"/>
    <!-- Alaska / Canada -->
    <path d="M 150 240 Q 200 180 280 190 Q 340 180 370 210 Q 320 230 260 220 Q 200 225 150 240 Z"/>
    <!-- Greenland -->
    <path d="M 380 190 Q 420 170 450 195 Q 430 220 390 210 Z" fill="#33475f"/>

    <!-- Central America & Caribbean -->
    <path d="M 230 360 Q 250 380 265 410 Q 255 415 240 390 Z"/>

    <!-- South America -->
    <path d="M 260 410 Q 300 400 340 430 Q 370 470 350 520 Q 320 570 290 580 Q 270 550 270 490 Q 250 440 260 410 Z"/>

    <!-- Europe -->
    <path d="M 480 220 Q 520 190 570 200 Q 600 220 590 250 Q 560 265 520 255 Q 490 245 480 220 Z"/>
    <!-- British Isles -->
    <path d="M 490 215 Q 505 200 515 210 Q 505 230 490 225 Z" fill="#33475f"/>
    <!-- Scandinavia -->
    <path d="M 540 175 Q 570 160 590 185 Q 575 210 550 200 Z"/>

    <!-- Africa -->
    <path d="M 470 280 Q 550 270 600 300 Q 620 360 590 420 Q 560 490 530 500 Q 500 450 470 380 Q 450 330 470 280 Z"/>
    <!-- Madagascar -->
    <path d="M 610 440 Q 625 435 620 465 Q 605 470 610 440 Z"/>

    <!-- Asia (Central, Russia, China, India, SE Asia) -->
    <path d="M 590 210 Q 670 170 780 180 Q 860 200 880 250 Q 850 280 800 270 Q 750 260 710 280 Q 660 290 620 260 Z"/>
    <!-- Middle East -->
    <path d="M 580 270 Q 640 260 660 290 Q 630 330 590 320 Z"/>
    <!-- India (South Asia) -->
    <path d="M 690 300 Q 730 295 750 325 Q 730 380 700 395 Q 685 350 690 300 Z"/>
    <!-- Bangladesh & Bay of Bengal delta -->
    <path d="M 740 330 Q 755 325 765 340 Q 755 360 740 355 Z" fill="#10b981"/>
    <!-- East Asia (China/Korea) -->
    <path d="M 780 260 Q 840 250 860 290 Q 830 340 780 330 Z"/>
    <!-- Japan -->
    <path d="M 880 260 Q 900 250 905 280 Q 890 305 875 285 Z" fill="#33475f"/>
    <!-- Southeast Asia & Malaysia / Indonesia -->
    <path d="M 770 360 Q 810 370 820 410 Q 790 430 765 390 Z"/>
    <!-- Singapore island point -->
    <circle cx="785" cy="425" r="4" fill="#ef4444"/>

    <!-- Australia & Oceania -->
    <path d="M 830 450 Q 910 430 940 470 Q 930 540 880 550 Q 830 520 830 450 Z"/>
    <!-- New Zealand -->
    <path d="M 960 520 Q 975 510 970 540 Q 950 545 960 520 Z"/>
  </g>

  <!-- Flight / Data Routes Curved Lines across Globe -->
  <!-- US to UK -->
  <path d="M 280 290 Q 380 220 505 220" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 4" opacity="0.6"/>
  <!-- UK to Frankfurt -->
  <path d="M 505 220 Q 530 215 550 230" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 4" opacity="0.6"/>
  <!-- Frankfurt to Mumbai -->
  <path d="M 550 230 Q 630 260 715 340" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 4" opacity="0.6"/>
  <!-- Mumbai to Dhaka -->
  <path d="M 715 340 Q 735 340 752 338" stroke="#10b981" stroke-width="2" stroke-linecap="round"/>
  <!-- Dhaka to Singapore -->
  <path d="M 752 338 Q 770 380 785 425" stroke="#10b981" stroke-width="2" stroke-linecap="round"/>
  <!-- Singapore to Tokyo -->
  <path d="M 785 425 Q 850 360 890 280" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 4" opacity="0.6"/>
  <!-- Singapore to Sydney -->
  <path d="M 785 425 Q 840 460 900 500" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 4" opacity="0.6"/>
</svg>
"""

with open('d:/hosting/static/images/curved-world-map.svg', 'w', encoding='utf-8') as f:
    f.write(curved_map_svg.strip())

print("Generated: d:/hosting/static/images/curved-world-map.svg")
