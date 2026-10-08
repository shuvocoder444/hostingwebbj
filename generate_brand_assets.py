import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs('static/img', exist_ok=True)
os.makedirs('staticfiles/img', exist_ok=True)
os.makedirs('mediafiles', exist_ok=True)

def create_transparent_logo():
    # Create transparent PNG 600x140
    img = Image.new('RGBA', (600, 140), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Try default font or basic shapes
    # Draw a stylish hex/cloud icon on the left
    # Outer circle/hexagon
    draw.rounded_rectangle([20, 20, 120, 120], radius=24, fill=(37, 99, 235, 255))
    
    # Bolt inside icon
    bolt_points = [(75, 35), (50, 75), (70, 75), (60, 105), (90, 65), (70, 65)]
    draw.polygon(bolt_points, fill=(255, 255, 255, 255))
    
    # Text: "VeloHoster"
    try:
        font = ImageFont.truetype("arial.ttf", 54)
        sub_font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
        sub_font = ImageFont.load_default()
        
    draw.text((145, 32), "Velo", fill=(15, 23, 42, 255), font=font)
    draw.text((260, 32), "Hoster", fill=(37, 99, 235, 255), font=font)
    draw.text((148, 92), "NEXT-GEN CLOUD & BDIX HOSTING", fill=(100, 116, 139, 255), font=sub_font)
    
    for path in ['static/img/logo.png', 'staticfiles/img/logo.png', 'mediafiles/logo.png']:
        img.save(path, 'PNG')
    print("Logo PNG created.")

def create_favicon():
    # 64x64 transparent favicon
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 60, 60], radius=14, fill=(37, 99, 235, 255))
    bolt_points = [(38, 14), (24, 34), (35, 34), (30, 50), (46, 29), (35, 29)]
    draw.polygon(bolt_points, fill=(255, 255, 255, 255))
    
    for path in ['static/img/favicon.png', 'staticfiles/img/favicon.png', 'static/img/favicon.ico', 'staticfiles/img/favicon.ico', 'mediafiles/favicon.png']:
        img.save(path, 'PNG' if path.endswith('.png') else 'ICO')
    print("Favicon created.")

def create_og_thumbnail():
    # 1200x630 for Facebook, WhatsApp, Twitter, Telegram, LinkedIn
    img = Image.new('RGB', (1200, 630), (10, 10, 18))
    draw = ImageDraw.Draw(img)
    
    # Gradient/glow effect lines
    draw.rectangle([0, 0, 1200, 8], fill=(37, 99, 235))
    draw.rounded_rectangle([40, 40, 1160, 590], radius=32, outline=(30, 41, 59), width=2)
    
    # Brand Badge
    draw.rounded_rectangle([80, 80, 200, 200], radius=36, fill=(37, 99, 235))
    bolt_points = [(150, 100), (120, 145), (145, 145), (135, 180), (170, 135), (145, 135)]
    draw.polygon(bolt_points, fill=(255, 255, 255))
    
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 68)
        tag_font = ImageFont.truetype("arialbd.ttf", 28)
        desc_font = ImageFont.truetype("arial.ttf", 26)
        badge_font = ImageFont.truetype("arialbd.ttf", 20)
    except Exception:
        title_font = ImageFont.load_default()
        tag_font = ImageFont.load_default()
        desc_font = ImageFont.load_default()
        badge_font = ImageFont.load_default()
        
    draw.text((230, 95), "VeloHoster", fill=(255, 255, 255), font=title_font)
    draw.text((235, 170), "HIGH PERFORMANCE CLOUD WEB HOSTING & DOMAINS", fill=(96, 165, 250), font=tag_font)
    
    # Feature Pills
    pills = [
        ("NVMe PCIe Gen4", (16, 185, 129)),
        ("LiteSpeed Enterprise", (59, 130, 246)),
        ("BDIX Direct <5ms", (245, 158, 11)),
        ("cPanel & AutoSSL", (168, 85, 247)),
        ("Instant Auto-Setup", (236, 72, 153)),
    ]
    x = 80
    for text, color in pills:
        draw.rounded_rectangle([x, 260, x + 200, 310], radius=16, fill=(20, 25, 40), outline=color, width=2)
        draw.text((x + 18, 273), text, fill=(240, 240, 250), font=badge_font)
        x += 215
        
    # Subtitle / description
    desc1 = "Deploy your website on lightning-fast NVMe cloud infrastructure."
    desc2 = "Singapore, USA, Germany, and Bangladesh BDIX datacenter network."
    desc3 = "Official cPanel, daily backups & instant payment gateway automation."
    draw.text((80, 360), desc1, fill=(203, 213, 225), font=desc_font)
    draw.text((80, 405), desc2, fill=(148, 163, 184), font=desc_font)
    draw.text((80, 450), desc3, fill=(148, 163, 184), font=desc_font)
    
    # Bottom URL bar
    draw.rounded_rectangle([80, 515, 1120, 565], radius=14, fill=(15, 23, 42))
    draw.text((105, 526), "WWW.VELOHOSTER.COM", fill=(56, 189, 248), font=tag_font)
    draw.text((850, 528), "24/7 Live WhatsApp Support", fill=(52, 211, 153), font=badge_font)
    
    for path in ['static/img/og_thumbnail.png', 'staticfiles/img/og_thumbnail.png', 'mediafiles/og_thumbnail.png']:
        img.save(path, 'PNG')
    print("OG Thumbnail PNG (1200x630) created.")

if __name__ == '__main__':
    create_transparent_logo()
    create_favicon()
    create_og_thumbnail()

