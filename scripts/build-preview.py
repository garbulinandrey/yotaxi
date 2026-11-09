"""Build an isolated hosting preview; never copies credentials or PHP handlers."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'booking-preview'
folder.mkdir(exist_ok=True)
for filename in ('callback.js', 'mobile.js', 'privacy.js', 'privacy.html', 'consent.html'):
    text = (root / filename).read_text()
    if filename.endswith('.html'):
        text = text.replace('href="./"', 'href="../booking-preview.html"')
    (folder / filename).write_text(text)
(folder / 'site.css').write_text((root / 'site.css').read_text().replace("url('photo.avif')", "url('../photo.avif')"))
text = (root / 'index.html').read_text().replace('<meta name="robots" content="index, follow">', '<meta name="robots" content="noindex, nofollow">')
text = text.replace('href="site.css?v=', 'href="booking-preview/site.css?v=')
for filename in ('callback.js', 'mobile.js', 'privacy.js'):
    text = text.replace('src="' + filename + '?v=', 'src="booking-preview/' + filename + '?v=')
for filename in ('privacy.html', 'consent.html'):
    text = text.replace('href="' + filename + '"', 'href="booking-preview/' + filename + '"')
(root / 'booking-preview.html').write_text(text)
print('Preview built: booking-preview.html and booking-preview/.')
