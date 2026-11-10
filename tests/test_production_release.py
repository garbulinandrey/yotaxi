"""Check that the complete release indexes the real homepage and includes matching assets."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]

class Assets(HTMLParser):
    def __init__(self, text): super().__init__(); self.links=[]; self.feed(text)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag in ('script','link','a','img'):
            value=a.get('src',a.get('href','')); path=urlsplit(value)
            if value and not path.scheme and not value.startswith('#'): self.links.append(path.path)

class ProductionReleaseTests(unittest.TestCase):
    def test_indexable_homepage_and_complete_asset_set(self):
        with ZipFile(ROOT/'releases/yotaxi-main-20261110.zip') as z:
            self.assertIsNone(z.testzip())
            names=set(z.namelist()); self.assertEqual(len(names),20)
            self.assertTrue({'index.html','robots.txt','sitemap.xml'} <= names)
            page=z.read('index.html').decode()
            self.assertIn('<meta name="robots" content="index, follow">',page)
            self.assertIn('<link rel="canonical" href="https://yotaxi.ru/">',page)
            self.assertNotIn('content="noindex',page)
            for value in ('id="cb-consent"','id="vehicleDialog"','class="mobile-request"'):
                self.assertIn(value,page)
            for path in Assets(page).links:
                if path.startswith('assets-v20261110/'):
                    self.assertIn(path,names)
                elif path:
                    self.assertTrue((ROOT/path).is_file(),path)
            self.assertNotIn('wa.me',page)
            self.assertNotIn('whatsapp',page.lower())
            self.assertIn('src="logo-central.png?v=20261110-1"',page)
            self.assertTrue({'logo-central.png','favicon.ico','favicon-48x48.png','site.webmanifest'} <= names)
            self.assertNotIn('href="site.css',page)
            self.assertNotIn('src="callback.js',page)
            self.assertIn("fetch('send-booking.php'",z.read('assets-v20261110/callback.js').decode())
            self.assertFalse(any(name.endswith('.php') or '.env' in name or '.htaccess' in name for name in names))
            source=(ROOT/'index.html').read_text()
            self.assertEqual(page[page.index('<body>'):].replace('assets-v20261110/',''),source[source.index('<body>'):])
            for name in ('robots.txt','sitemap.xml'):
                self.assertEqual(z.read(name),(ROOT/name).read_bytes())

if __name__ == '__main__':unittest.main()
