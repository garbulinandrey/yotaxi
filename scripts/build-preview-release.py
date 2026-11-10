"""Package one complete isolated preview; never includes private files or PHP."""
from pathlib import Path
import runpy
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
runpy.run_path(str(root / 'scripts/build-preview.py'))
release = root / 'releases/booking-mobile-20261110.zip'
release.parent.mkdir(exist_ok=True)
page = (root / 'booking-preview.html').read_text().replace('booking-preview/', 'booking-mobile/')
page = page.replace('<meta charset="UTF-8">', '<meta charset="UTF-8"><meta name="application-version" content="booking-mobile-20261110">')
with ZipFile(release, 'w', ZIP_DEFLATED) as archive:
    archive.writestr('booking-mobile.html', page)
    for name in ('site.css', 'callback.js', 'mobile.js', 'privacy.js', 'privacy.html', 'consent.html'):
        text = (root / 'booking-preview' / name).read_text()
        if name.endswith('.html'):
            text = text.replace('../booking-preview.html', '../booking-mobile.html')
        archive.writestr('booking-mobile/' + name, text)
with ZipFile(release) as archive:
    assert archive.testzip() is None
    assert 'id="cb-consent"' in archive.read('booking-mobile.html').decode()
print(str(release))
