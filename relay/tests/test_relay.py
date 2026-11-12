import concurrent.futures
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Relay


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'leads.sqlite3'
        self.sent = []
        self.secret = 'a' * 64
        self.relay = Relay(self.database, self.secret, 'fixture-token', 'fixture-chat', self.send)
        self.now = 1800000000

    def send(self, name, phone, vehicle=""):
        self.sent.append((name, phone, vehicle))
        return 'sent'

    def request(self, data=None, stamp=None, signature=None, relay=None):
        if data is None:
            data = {'request_id': '1' * 32, 'name': 'Анна', 'phone': '+79991234567'}
        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        stamp = str(self.now) if stamp is None else stamp
        if signature is None:
            signature = hmac.new(self.secret.encode(), stamp.encode() + b'\n' + raw, hashlib.sha256).hexdigest()
        return (relay or self.relay).handle(raw, stamp, signature, self.now)

    def test_valid_request(self):
        self.assertEqual(self.request(), (200, {'status': 'success'}))
        self.assertEqual(len(self.sent), 1)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT state FROM leads').fetchone()[0], 'sent')

    def test_booking_is_persisted_and_different_models_are_not_duplicates(self):
        data = {'request_id': '1'*32, 'name': 'Анна', 'phone': '+79991234567',
                'vehicle': 'haval-buyout', 'consent_version': '2026-11-09'}
        self.assertEqual(self.request(data), (200, {'status': 'success', 'vehicle': 'haval-buyout'}))
        self.assertEqual(self.request(dict(data, request_id='2'*32))[0], 200)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][2], 'haval-buyout')
        self.assertEqual(self.request(dict(data, request_id='3'*32, vehicle='jetta'))[0], 200)
        self.assertEqual(len(self.sent), 2)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT vehicle,consent_version FROM leads ORDER BY id LIMIT 1').fetchone(),
                             ('haval-buyout', '2026-11-09'))

    def test_invalid_booking_never_sends(self):
        data = {'request_id': '1'*32, 'name': 'Анна', 'phone': '+79991234567', 'vehicle': 'jetta'}
        for changes in ({}, {'vehicle': 'fake-car'}, {'vehicle': []}, {'consent_version': []}):
            self.assertEqual(self.request(dict(data, **changes))[0], 422)
        self.assertEqual(self.sent, [])

    def test_existing_database_migrates_without_losing_old_leads(self):
        path = Path(self.temp.name) / 'old.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE leads (id TEXT PRIMARY KEY, digest TEXT NOT NULL, fingerprint TEXT NOT NULL, created INTEGER NOT NULL, state TEXT NOT NULL, name TEXT NOT NULL, phone TEXT NOT NULL)')
            db.execute("INSERT INTO leads VALUES ('old','digest','fingerprint',1,'sent','Анна','+79991234567')")
        for _ in range(2):
            Relay(path, self.secret, 'fixture-token', 'fixture-chat', self.send)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('SELECT name,vehicle,consent_version FROM leads').fetchone(), ('Анна','',''))

    def test_booking_message_contains_model_and_contact_without_claiming_confirmation(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return b'{"ok":true}'
        from urllib.parse import parse_qs
        with patch('app.urllib.request.urlopen', return_value=Response()) as opener:
            self.assertEqual(self.relay.send_telegram('Анна', '+79991234567', 'haval-buyout'), 'sent')
        text = parse_qs(opener.call_args.args[0].data.decode())['text'][0]
        self.assertIn('Haval Jolion 2025 — выкуп', text)
        self.assertIn('Анна', text)
        self.assertIn('+79991234567', text)

    def test_unauthorized_and_stale_requests_never_send(self):
        for stamp, signature in [(str(self.now), '0' * 64), (str(self.now - 301), None),
                                 ('bad', None), (str(self.now), 'я' * 64)]:
            self.assertEqual(self.request(stamp=stamp, signature=signature)[0], 403)
        self.assertEqual(self.sent, [])

    def test_validation_and_size(self):
        for data in [b'not json', [], {'name': 'Анна'},
                     {'request_id': '1'*32, 'name': '<script>', 'phone': '+79991234567'},
                     {'request_id': '1'*32, 'name': 'Анна', 'phone': 'abc'}]:
            self.assertEqual(self.request(data)[0], 422)
        self.assertEqual(self.request(b'x' * 4097)[0], 413)
        self.assertEqual(self.sent, [])

    def test_replay_same_id_and_same_contact_are_deduplicated(self):
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request({'request_id': '2'*32, 'name': 'Анна', 'phone': '+79991234567'})[0], 200)
        self.assertEqual(len(self.sent), 1)

    def test_same_id_different_body_is_rejected(self):
        self.request()
        self.assertEqual(self.request({'request_id': '1'*32, 'name': 'Борис', 'phone': '+79991234567'})[0], 409)
        self.assertEqual(len(self.sent), 1)

    def test_ambiguous_failure_is_saved_and_not_automatically_resent(self):
        self.relay.transport = lambda *args: 'unknown'
        code, result = self.request()
        self.assertEqual(code, 502)
        self.assertTrue(result['saved'])
        restarted = Relay(self.database, self.secret, 'fixture-token', 'fixture-chat', self.send)
        self.assertEqual(self.request(relay=restarted)[0], 503)
        self.assertEqual(self.request({'request_id': '2'*32, 'name': 'Анна', 'phone': '+79991234567'}, relay=restarted)[0], 503)
        self.assertEqual(self.sent, [])

    def test_definite_failure_permits_a_new_attempt(self):
        self.relay.transport = lambda *args: 'failed'
        self.assertEqual(self.request()[0], 502)
        self.relay.transport = self.send
        self.assertEqual(self.request({'request_id': '2'*32, 'name': 'Анна', 'phone': '+79991234567'})[0], 200)
        self.assertEqual(len(self.sent), 1)

    def test_concurrent_duplicates_do_not_both_send(self):
        entered, release = threading.Event(), threading.Event()
        def send(name, phone):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('test synchronization failed')
            return self.send(name, phone)
        self.relay.transport = send
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            first = pool.submit(self.request)
            self.assertTrue(entered.wait(3))
            second = self.request({'request_id': '2'*32, 'name': 'Анна', 'phone': '+79991234567'})
            release.set()
            self.assertEqual(first.result()[0], 200)
            self.assertEqual(second[0], 503)
        self.assertEqual(len(self.sent), 1)

    def test_rate_limit(self):
        for i in range(30):
            self.assertEqual(self.request({'request_id': format(i, '032x'), 'name': 'Анна', 'phone': '+7'+str(9000000000+i)})[0], 200)
        self.assertEqual(self.request({'request_id': 'f'*32, 'name': 'Анна', 'phone': '+78881234567'})[0], 429)

    def test_telegram_transport_is_post_and_not_html(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self, *args):pass
            def read(self, limit):return b'{"ok":true}'
        with patch('app.urllib.request.urlopen', return_value=Response()) as opener:
            self.assertEqual(self.relay.send_telegram('Анна', '+79991234567'), 'sent')
        request = opener.call_args.args[0]
        self.assertEqual(request.method, 'POST')
        self.assertNotIn('79991234567', request.full_url)
        self.assertIn(b'chat_id=', request.data)
        self.assertNotIn(b'parse_mode=', request.data)


if __name__ == '__main__':
    unittest.main()
