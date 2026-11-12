"""Signed website leads -> Telegram. No polling and no client-selected destinations."""
import hashlib
import hmac
import json
import os
import re
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


VEHICLES = {'vesta-2019-21': 'Lada Vesta 2019–2021 — аренда', 'vesta-2023': 'Lada Vesta NG 2023 — аренда', 'solaris-manual': 'Solaris МКПП — аренда', 'solaris-auto': 'Solaris АКПП — аренда', 'jetta': 'Jetta VA3 — аренда', 'solaris-2024': 'Solaris АКПП 2024 — аренда', 'solaris-2025': 'Solaris АКПП 2025 — аренда', 'haval-rent': 'Haval Jolion 2025 — аренда', 'haval-buyout': 'Haval Jolion 2025 — выкуп'}
CONSENT_VERSION = "2026-11-09"

class Relay:
    def __init__(self, database, secret, token, chat_id, transport=None):
        if not re.fullmatch(r'[a-f0-9]{64}', secret):
            raise ValueError('RELAY_SECRET must contain 64 lowercase hex characters')
        if not token or not chat_id:
            raise ValueError('Missing Telegram configuration')
        self.secret = secret.encode()
        self.token, self.chat_id = token, chat_id
        self.database = str(database)
        self.transport = transport or self.send_telegram
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY, digest TEXT NOT NULL, fingerprint TEXT NOT NULL,
                created INTEGER NOT NULL, state TEXT NOT NULL,
                name TEXT NOT NULL, phone TEXT NOT NULL)''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(leads)')}
            for column in ('vehicle', 'consent_version'):
                if column not in columns:
                    db.execute(f"ALTER TABLE leads ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            db.execute('CREATE INDEX IF NOT EXISTS lead_fingerprint ON leads(fingerprint, created)')
        os.chmod(database, 0o600)

    def connect(self):
        return sqlite3.connect(self.database, timeout=5)

    def send_telegram(self, name, phone, vehicle=""):
        body = urllib.parse.urlencode({
            'chat_id': self.chat_id,
            'text': (('🚗 БРОНИРОВАНИЕ (Сайт)\nАвтомобиль: ' + VEHICLES[vehicle]) if vehicle else '🔔 НОВАЯ ЗАЯВКА (Сайт)') + '\n\n👤 Имя: ' + name + '\n📱 Телефон: ' + phone,
        }).encode()
        request = urllib.request.Request(
            'https://api.telegram.org/bot' + self.token + '/sendMessage',
            data=body, headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read(65536))
            return 'sent' if payload.get('ok') is True else 'failed'
        except urllib.error.HTTPError as exc:
            # API 4xx definitively rejects delivery. Other failures may be ambiguous.
            return 'failed' if exc.code in (400, 401, 403, 404, 429) else 'unknown'
        except (OSError, ValueError, urllib.error.URLError):
            return 'unknown'

    def handle(self, raw, stamp, signature, now=None):
        now = int(time.time()) if now is None else now
        if len(raw) > 4096:
            return 413, {'status': 'error'}
        if not re.fullmatch(r'[0-9]{10,12}', stamp or '') or abs(now - int(stamp)) > 300:
            return 403, {'status': 'error'}
        if not re.fullmatch(r'[a-f0-9]{64}', signature or ''):
            return 403, {'status': 'error'}
        expected = hmac.new(self.secret, stamp.encode() + b'\n' + raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ''):
            return 403, {'status': 'error'}
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            vehicle = data.get('vehicle', '')
            consent = data.get('consent_version', '')
            if not isinstance(vehicle, str) or (vehicle and vehicle not in VEHICLES):
                raise ValueError()
            if not isinstance(consent, str) or (vehicle and consent != CONSENT_VERSION):
                raise ValueError()
            request_id, name, phone = data.get('request_id'), data.get('name'), data.get('phone')
            if not isinstance(request_id, str) or not re.fullmatch(r'[a-f0-9]{32}', request_id):
                raise ValueError()
            if not isinstance(name, str) or not 2 <= len(name) <= 80:
                raise ValueError()
            if any(not (c.isalpha() or c in " '-’" or '\u0300' <= c <= '\u036f') for c in name):
                raise ValueError()
            if not isinstance(phone, str) or not re.fullmatch(r'\+7[0-9]{10}', phone):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            return 422, {'status': 'error'}
        success = {'status': 'success'}
        if vehicle:
            success['vehicle'] = vehicle
        digest = hashlib.sha256(raw).hexdigest()
        fingerprint = hmac.new(self.secret, (name.casefold() + '\n' + phone + ('\n' + vehicle if vehicle else '')).encode(), hashlib.sha256).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Retain contacts for seven days; no personal data in HTTP/application logs.
            db.execute('DELETE FROM leads WHERE created < ?', (now - 7 * 86400,))
            old = db.execute('SELECT digest, state FROM leads WHERE id = ?', (request_id,)).fetchone()
            if old:
                if old[0] != digest:
                    return 409, {'status': 'error'}
                return (200, success) if old[1] == 'sent' else (503, {'status': 'error', 'saved': True})
            duplicate = db.execute('SELECT state FROM leads WHERE fingerprint = ? AND created > ? ORDER BY created DESC LIMIT 1',
                                   (fingerprint, now - 600)).fetchone()
            if duplicate and duplicate[0] in ('sent', 'pending', 'unknown'):
                return (200, success) if duplicate[0] == 'sent' else (503, {'status': 'error', 'saved': True})
            if db.execute('SELECT COUNT(*) FROM leads WHERE created > ?', (now - 60,)).fetchone()[0] >= 30:
                return 429, {'status': 'error'}
            db.execute('INSERT INTO leads (id, digest, fingerprint, created, state, name, phone, vehicle, consent_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (request_id, digest, fingerprint, now, 'pending', name, phone, vehicle, consent))
        # Persist before contacting Telegram. Ambiguous failures are not automatically
        # retried: Telegram has no sendMessage idempotency key and may have delivered.
        try:
            state = self.transport(name, phone, vehicle) if vehicle else self.transport(name, phone)
        except Exception:
            state = 'unknown'
        if state not in ('sent', 'failed', 'unknown'):
            state = 'unknown'
        with self.connect() as db:
            db.execute('UPDATE leads SET state = ? WHERE id = ?', (state, request_id))
        return (200, success) if state == 'sent' else (502, {'status': 'error', 'saved': True})


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    slots = threading.BoundedSemaphore(8)

    def log_message(self, *args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def reply(self, code, result):
        body = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200 if self.path == '/health' else 404, {'status': 'ok' if self.path == '/health' else 'error'})

    def do_POST(self):
        if self.path != '/v1/leads':
            return self.reply(404, {'status': 'error'})
        if not self.slots.acquire(blocking=False):
            return self.reply(503, {'status': 'error'})
        try:
            length = self.headers.get('Content-Length', '')
            if not length.isdecimal() or not 0 < int(length) <= 4096 or self.headers.get('Transfer-Encoding'):
                return self.reply(413, {'status': 'error'})
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                return self.reply(400, {'status': 'error'})
            code, result = self.server.relay.handle(raw, self.headers.get('X-Yotaxi-Timestamp'),
                                                   self.headers.get('X-Yotaxi-Signature'))
            self.reply(code, result)
        except (TimeoutError, socket.timeout):
            self.close_connection = True
        except Exception:
            self.reply(503, {'status': 'error'})
        finally:
            self.slots.release()


if __name__ == '__main__':
    os.umask(0o077)
    relay = Relay('/data/leads.sqlite3', os.environ.get('RELAY_SECRET', ''),
                  os.environ.get('BOT_TOKEN', ''), os.environ.get('MANAGER_CHAT_ID', ''))
    server = ThreadingHTTPServer(('0.0.0.0', 8000), Handler)
    server.relay = relay
    print('Relay listening; logs contain no lead data.', flush=True)
    server.serve_forever()
