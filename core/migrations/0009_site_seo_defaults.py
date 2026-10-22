from django.db import migrations, models


OLD_DESCRIPTION = (
    'Best web hosting in Bangladesh (bangladesher hosting) & cheap domain registration (kom dame domain). '
    'Ultra-fast BDIX, Singapore, USA & Germany NVMe cPanel hosting. Top Hostinger & Namecheap alternative '
    'with instant bKash, Nagad payment & 24/7 Bangla support.'
)
OLD_KEYWORDS = (
    'namecheap, hostinger, hostingbd, web hosting, domain, besthosing bangladesh, best hosting bangladesh, '
    'cheap domain, kom dame domain, bangladeseher hosting, bangladesher hosting, bdx hosting, bdix hosting, '
    'singapur hosting, singapore hosting, usa hosting, garmany hosting, germany hosting, erup hosting, '
    'europe hosting, cpanel hosting, buy domain bangladesh, bkash hosting'
)


def clean_stock_seo_defaults(apps, schema_editor):
    SiteSetting = apps.get_model('core', 'SiteSetting')
    SiteSetting.objects.filter(site_title__contains='Best Hosting in Bangladesh').update(
        site_title='VeloHoster: NVMe Web Hosting and Domains in Bangladesh'
    )
    SiteSetting.objects.filter(meta_description=OLD_DESCRIPTION).update(
        meta_description=(
            'NVMe web hosting and domain registration with cPanel, reliable support, and server locations '
            'in Bangladesh, Singapore, the USA, and Europe.'
        )
    )
    SiteSetting.objects.filter(meta_keywords=OLD_KEYWORDS).update(meta_keywords='')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_sitesetting_require_email_otp_and_more'),
    ]

    operations = [
        migrations.RunPython(clean_stock_seo_defaults, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='sitesetting',
            name='meta_description',
            field=models.TextField(
                default='NVMe web hosting and domain registration with cPanel, reliable support, and server locations in Bangladesh, Singapore, the USA, and Europe.',
                help_text='Meta description for Google SEO and social share previews (Facebook, WhatsApp, Twitter).',
            ),
        ),
        migrations.AlterField(
            model_name='sitesetting',
            name='meta_keywords',
            field=models.TextField(blank=True, default='', help_text='Comma-separated SEO keywords and tags.'),
        ),
        migrations.AlterField(
            model_name='sitesetting',
            name='site_title',
            field=models.CharField(
                default='VeloHoster: NVMe Web Hosting and Domains in Bangladesh',
                help_text='Main website title shown in search engines and social share previews.',
                max_length=200,
            ),
        ),
    ]
