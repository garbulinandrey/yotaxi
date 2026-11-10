"""Technical SEO consistency checks; no external services or ranking claims."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]

class Head(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.tags = []; self.feed(text)
    def handle_starttag(self, tag, attrs): self.tags.append((tag, dict(attrs)))
    def find(self, tag, key, value): return [attrs for name, attrs in self.tags if name == tag and attrs.get(key) == value]

class SEOTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT/'index.html').read_text(); self.head = Head(self.text)
    def test_single_main_metadata_and_h1(self):
        self.assertEqual(len(re.findall(r'<title>', self.text)), 1)
        self.assertEqual(len(re.findall(r'<h1\b', self.text)), 1)
        self.assertEqual(len(self.head.find('meta','name','description')), 1)
        self.assertEqual([x['href'] for x in self.head.find('link','rel','canonical')], ['https://yotaxi.ru/'])
        self.assertEqual(self.head.find('meta','name','robots')[0]['content'], 'index, follow')
        self.assertNotIn('meta name="keywords"', self.text)
    def test_social_preview_points_to_existing_image(self):
        image = self.head.find('meta','property','og:image')[0]['content']
        self.assertTrue((ROOT/image.removeprefix('https://yotaxi.ru/')).is_file())
        self.assertNotIn('og-image.jpg', self.text)
    def test_structured_data_matches_prices_and_visible_answers(self):
        business, faq = [json.loads(t) for t in re.findall(r'<script type="application/ld\+json">(.*?)</script>',self.text,re.S)]
        self.assertEqual(business['@type'], 'AutoRental')
        offers = business['hasOfferCatalog']['itemListElement']
        self.assertEqual([o['priceSpecification']['minPrice'] for o in offers[:9]], [1700,1900,1900,2100,2200,2400,2500,2900,3500])
        self.assertNotIn('aggregateRating', business)
        self.assertNotIn('geo', business)
        self.assertEqual(len(faq['mainEntity']),6)
        for item in faq['mainEntity']:
            self.assertIn(item['name'], self.text)
            self.assertIn(item['acceptedAnswer']['text'], self.text)
    def test_one_robots_group_and_render_assets_accessible(self):
        text=(ROOT/'robots.txt').read_text(); robot=RobotFileParser();robot.parse(text.splitlines())
        self.assertEqual(len(re.findall(r'^User-agent:',text,re.M)),1)
        for agent in ['Googlebot','Yandex','*']:
            for path in ['/','/site.css','/mobile.js','/vesta23.jpg','/booking-preview.html','/?utm_source=test']:
                self.assertTrue(robot.can_fetch(agent,'https://yotaxi.ru'+path),(agent,path))
            for path in ['/cgi-bin/php5.cgi','/send.php','/send-booking.php']:
                self.assertFalse(robot.can_fetch(agent,'https://yotaxi.ru'+path),(agent,path))
    def test_sitemap_contains_only_canonical_homepage(self):
        tree=ET.fromstring((ROOT/'sitemap.xml').read_text());ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
        self.assertEqual([n.text for n in tree.findall('s:url/s:loc',ns)],['https://yotaxi.ru/'])
        self.assertEqual(tree.findall('s:url/s:lastmod',ns),[])
    def test_all_preview_variants_remain_noindex(self):
        self.assertIn('noindex',Head((ROOT/'booking-preview.html').read_text()).find('meta','name','robots')[0]['content'])
        with ZipFile(ROOT/'releases/booking-mobile-gallery-20261110.zip') as z:
            self.assertIn('noindex',Head(z.read('booking-mobile.html').decode()).find('meta','name','robots')[0]['content'])
    def test_seo_support_archive_has_no_website_or_private_files(self):
        with ZipFile(ROOT/'releases/yotaxi-seo-support-20261110.zip') as z:
            self.assertEqual(set(z.namelist()),{'robots.txt','sitemap.xml'})
            self.assertEqual(z.read('robots.txt'),(ROOT/'robots.txt').read_bytes())

if __name__ == '__main__': unittest.main()
