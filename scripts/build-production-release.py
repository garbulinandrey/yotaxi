"""Build a production homepage with isolated, matching public assets."""
from pathlib import Path
import hashlib
import json
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
out = root / 'deploy/production'
namespace = 'assets-v20261110'
assets = out / namespace
assets.mkdir(parents=True, exist_ok=True)
files = ('site.css', 'callback.js', 'mobile.js', 'vehicle.js', 'vehicle-galleries.json', 'privacy.js', 'privacy.html', 'consent.html')
for name in files:
    text = (root / name).read_text()
    if name == 'site.css':
        text = text.replace("url('photo.avif')", "url('../photo.avif')").replace("url('max2.png')", "url('../max2.png')")
    if name.endswith('.html'):
        text = text.replace('href="./"', 'href="../"')
    (assets / name).write_text(text)
source = (root / 'index.html').read_text()
page = source.replace('href="site.css?v=', 'href="' + namespace + '/site.css?v=')
for name in ('callback.js', 'mobile.js', 'vehicle.js', 'privacy.js'):
    page = page.replace('src="' + name + '?v=', 'src="' + namespace + '/' + name + '?v=')
for name in ('privacy.html', 'consent.html'):
    page = page.replace('href="' + name + '"', 'href="' + namespace + '/' + name + '"')
assert '<meta name="robots" content="index, follow">' in page
assert '<link rel="canonical" href="https://yotaxi.ru/">' in page
assert 'booking-preview/' not in page and 'booking-mobile/' not in page
assert page[page.index('<body>'):].replace(namespace + '/', '') == source[source.index('<body>'):]
(out / 'index.html').write_text(page)
branding = ('logo-central.png', 'favicon.ico', 'favicon-32x32.png', 'favicon-48x48.png', 'favicon-96x96.png', 'apple-touch-icon.png', 'android-chrome-192x192.png', 'android-chrome-512x512.png', 'site.webmanifest', 'max2.png')
for name in ('robots.txt', 'sitemap.xml') + branding:
    shutil.copyfile(root / name, out / name)
archive = root / 'releases/yotaxi-main-20261110.zip'
with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
    for name in ('index.html', 'robots.txt', 'sitemap.xml') + branding:
        z.write(out / name, name)
    for name in files:
        z.write(assets / name, namespace + '/' + name)
with ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('.env' in name or name.endswith('.php') for name in z.namelist())
    print('Complete production archive:', len(z.namelist()), 'files')
proof = {'release': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
         'canonical': 'https://yotaxi.ru/', 'robots': 'index, follow',
         'assets_namespace': namespace, 'existing_images_required': True,
         'form_endpoint': 'send-booking.php', 'backend_changes': False,
         'source_ui_unchanged_except_asset_paths': True}
(out / 'verification.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
print(archive)
