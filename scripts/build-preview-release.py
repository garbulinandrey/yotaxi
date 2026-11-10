"""Package one complete isolated preview; never includes private files or PHP."""
from pathlib import Path
import runpy
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
runpy.run_path(str(root / 'scripts/build-preview.py'))
release = root / 'releases/booking-mobile-gallery-20261110.zip'
release.parent.mkdir(exist_ok=True)
page = (root / 'booking-preview.html').read_text().replace('booking-preview/', 'booking-mobile/')
page = page.replace('<meta charset="UTF-8">', '<meta charset="UTF-8"><meta name="application-version" content="booking-mobile-gallery-20261110">')
with ZipFile(release, 'w', ZIP_DEFLATED) as archive:
    archive.writestr('booking-mobile.html', page)
    for filename in ('logo-central.png', 'favicon.ico', 'favicon-32x32.png', 'favicon-48x48.png', 'favicon-96x96.png', 'apple-touch-icon.png', 'android-chrome-192x192.png', 'android-chrome-512x512.png', 'site.webmanifest'):
        archive.write(root / filename, filename)
    for name in ('site.css', 'callback.js', 'mobile.js', 'vehicle.js', 'vehicle-galleries.json', 'privacy.js', 'privacy.html', 'consent.html'):
        text = (root / 'booking-preview' / name).read_text()
        if name.endswith('.html'):
            text = text.replace('../booking-preview.html', '../booking-mobile.html')
        archive.writestr('booking-mobile/' + name, text)
with ZipFile(release) as archive:
    assert archive.testzip() is None
    assert 'id="cb-consent"' in archive.read('booking-mobile.html').decode()
print(str(release))
