"""Isolated PHP request tests. Telegram is replaced by a local stub; no network."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PHP = os.environ.get('PHP_BIN', 'php')
STUB = r'''<?php
if (extension_loaded('curl')) { fwrite(STDERR, 'Run tests with php -n, without curl'); exit(90); }
foreach (['CURLOPT_POST', 'CURLOPT_POSTFIELDS', 'CURLOPT_RETURNTRANSFER', 'CURLOPT_CONNECTTIMEOUT', 'CURLOPT_TIMEOUT', 'CURLOPT_FOLLOWLOCATION', 'CURLINFO_HTTP_CODE'] as $i => $key) define($key, $i + 1);
function curl_init($url) {
    if ($url !== 'https://api.telegram.org/botfixture-token/sendMessage') throw new Exception('Unexpected endpoint');
    return true;
}
function curl_setopt_array($ch, $options) {
    parse_str($options[CURLOPT_POSTFIELDS], $body);
    if ($options[CURLOPT_POST] !== true || $body['chat_id'] !== 'fixture-chat'
        || strpos($body['text'], '+79991234567') === false || isset($body['parse_mode'])
        || $options[CURLOPT_TIMEOUT] !== 12 || $options[CURLOPT_CONNECTTIMEOUT] !== 5
        || $options[CURLOPT_FOLLOWLOCATION] !== false) throw new Exception('Unsafe transport options');
}
function curl_exec($ch) {
    $mode = getenv('TEST_TELEGRAM_MODE');
    if ($mode === 'timeout') return false;
    if ($mode === 'invalid') return 'not-json';
    return json_encode(['ok' => $mode !== 'rejected', 'description' => 'private upstream diagnostic']);
}
function curl_getinfo($ch, $option) { return getenv('TEST_TELEGRAM_MODE') === 'http-error' ? 500 : 200; }
function curl_close($ch) {}
$_POST = json_decode(getenv('TEST_POST'), true);
$_SERVER['REQUEST_METHOD'] = getenv('TEST_METHOD');
$_SERVER['REMOTE_ADDR'] = '192.0.2.1';
$_SERVER['CONTENT_LENGTH'] = getenv('TEST_LENGTH');
register_shutdown_function(function () { fwrite(STDERR, (string) http_response_code()); });
require __DIR__ . '/public/send.php';
'''

class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'public').mkdir()
        (self.root / 'state').mkdir()
        shutil.copyfile(ROOT / 'send.php', self.root / 'public/send.php')
        (self.root / 'request.php').write_text(STUB)
        self.env = dict(os.environ, TMPDIR=str(self.root / 'state'),
                        TELEGRAM_TOKEN='fixture-token', TELEGRAM_CHAT_ID='fixture-chat')

    def request(self, post=None, method='POST', mode='success', length='100'):
        env = dict(self.env, TEST_POST=json.dumps(post if post is not None else {
            'name': 'Анна-Мария', 'phone': '8 (999) 123-45-67', 'website': '', 'consent': '2026-11-09'}),
                   TEST_METHOD=method, TEST_TELEGRAM_MODE=mode, TEST_LENGTH=length)
        result = subprocess.run([PHP, '-n', str(self.root / 'request.php')], env=env,
                                capture_output=True, text=True, check=True)
        return int(result.stderr), json.loads(result.stdout)

    def test_success_normalizes_phone_and_uses_post(self):
        code, body = self.request()
        self.assertEqual((code, body['status']), (200, 'success'))

    def test_invalid_inputs_do_not_send(self):
        for post in [{}, {'name': '<script>', 'phone': '123'},
                     {'name': ['Анна'], 'phone': '79991234567'},
                     {'name': 'Анна', 'phone': 'abc79991234567'},
                     {'name': 'А' * 81, 'phone': '79991234567'}]:
            self.assertEqual(self.request(post)[0], 422)

    def test_consent_and_vehicle_are_validated_before_delivery(self):
        base = {'name': 'Анна', 'phone': '79991234567'}
        self.assertEqual(self.request(base)[0], 422)
        self.assertEqual(self.request(dict(base, consent='wrong'))[0], 422)
        self.assertEqual(self.request(dict(base, consent='2026-11-09', vehicle='fake-car'))[0], 422)
        self.assertEqual(self.request(dict(base, consent='2026-11-09', vehicle=['jetta']))[0], 422)

    def test_honeypot_never_contacts_telegram(self):
        self.assertEqual(self.request({'website': 'spam'})[0], 200)
        self.assertFalse(list((self.root / 'state').rglob('requests.json')))

    def test_method_and_size(self):
        self.assertEqual(self.request(method='GET')[0], 405)
        self.assertEqual(self.request(length='9000')[0], 413)

    def test_upstream_failures_are_not_success_or_leaked(self):
        for mode in ['timeout', 'invalid', 'rejected', 'http-error']:
            code, body = self.request(mode=mode)
            self.assertEqual(code, 502)
            self.assertEqual(body['status'], 'error')
            self.assertNotIn('private', json.dumps(body))
            self.assertNotIn('fixture-token', json.dumps(body))

    def test_rate_limit_survives_separate_workers(self):
        for _ in range(5):
            self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.request()[0], 429)
        # A different connection address is a different limit bucket.
        runner = self.root / 'request.php'
        runner.write_text(STUB.replace('192.0.2.1', '192.0.2.2'))
        self.assertEqual(self.request()[0], 200)

    def test_private_env_and_missing_credentials(self):
        self.env['TELEGRAM_TOKEN'] = ''
        self.env['TELEGRAM_CHAT_ID'] = ''
        self.assertEqual(self.request()[0], 503)
        (self.root / '.yotaxi.env').write_text(
            '# private configuration\nTELEGRAM_TOKEN="fixture-token"\nTELEGRAM_CHAT_ID=fixture-chat\n')
        self.assertEqual(self.request()[0], 200)

if __name__ == '__main__':
    unittest.main()
