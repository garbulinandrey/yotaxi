"""Cross-language PHP signature tests; cURL and Telegram are both stubbed."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'relay'))
from app import Relay

STUB = r'''<?php
if (extension_loaded('curl')) exit(90);
foreach (['CURLOPT_POST', 'CURLOPT_POSTFIELDS', 'CURLOPT_RETURNTRANSFER', 'CURLOPT_CONNECTTIMEOUT', 'CURLOPT_TIMEOUT', 'CURLOPT_FOLLOWLOCATION', 'CURLINFO_HTTP_CODE', 'CURLOPT_HTTPHEADER', 'CURLOPT_RESOLVE'] as $i => $key) define($key, $i+1);
function curl_init($url) {
    if (!in_array($url, ['https://relay.example/v1/leads', 'https://relay.example:2053/yotaxi/v1/leads'], true)) throw new Exception('Unexpected endpoint');
    return true;
}
function curl_setopt_array($ch, $options) {
    if (!$options[CURLOPT_POST] || $options[CURLOPT_TIMEOUT] !== 15 || $options[CURLOPT_FOLLOWLOCATION] !== false) throw new Exception('Unsafe options');
    file_put_contents(getenv('TEST_CAPTURE'), json_encode(['body'=>$options[CURLOPT_POSTFIELDS], 'headers'=>$options[CURLOPT_HTTPHEADER]]));
}
function curl_setopt($ch, $option, $value) {
    if ($option !== CURLOPT_RESOLVE) throw new Exception('Unexpected option');
    $path=getenv('TEST_CAPTURE'); $data=json_decode(file_get_contents($path), true);
    $data['resolve']=$value; file_put_contents($path,json_encode($data));
}
function curl_exec($ch) {
    if (getenv('TEST_MODE') === 'timeout') return false;
    return getenv('TEST_MODE') === 'success' ? json_encode(['status'=>'success', 'vehicle'=>getenv('TEST_ACK') ?: '']) : '{"status":"error"}';
}
function curl_getinfo($ch, $option) {return getenv('TEST_MODE') === 'forbidden' ? 403 : (getenv('TEST_MODE') === 'timeout' ? 0 : 200);}
function curl_close($ch) {}
$_SERVER['REQUEST_METHOD']='POST'; $_SERVER['REMOTE_ADDR']='192.0.2.1';
$_POST=['name'=>'Анна', 'phone'=>'8 (999) 123-45-67', 'consent'=>'2026-11-09', 'vehicle'=>getenv('TEST_VEHICLE') ?: ''];
register_shutdown_function(function () {fwrite(STDERR,(string)http_response_code());});
require __DIR__ . '/public/send.php';
'''


class RelayPHPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'public').mkdir()
        (self.root / 'state').mkdir()
        shutil.copyfile(os.environ.get('RELAY_PHP_SOURCE', str(ROOT / 'send.php')), self.root / 'public/send.php')
        (self.root / 'test.php').write_text(STUB)
        self.secret = 'a' * 64

    def run_php(self, **changes):
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp(dir=self.root / 'state'), RELAY_URL='https://relay.example/v1/leads',
                   RELAY_SECRET=self.secret, TEST_CAPTURE=str(self.root / 'capture.json'), TEST_MODE='success')
        env.update(changes)
        result = subprocess.run([os.environ.get('PHP_BIN','php'), '-n', str(self.root/'test.php')],
                                capture_output=True, text=True, env=env, check=True)
        return int(result.stderr), json.loads(result.stdout)

    def test_php_signature_is_accepted_by_python_receiver(self):
        code, result = self.run_php()
        self.assertEqual((code, result['status']), (200, 'success'))
        capture = json.loads((self.root / 'capture.json').read_text())
        headers = dict(h.split(': ',1) for h in capture['headers'])
        body = capture['body'].encode()
        timestamp = headers['X-Yotaxi-Timestamp']
        signature = headers['X-Yotaxi-Signature']
        self.assertEqual(signature, hmac.new(self.secret.encode(), timestamp.encode()+b'\n'+body, hashlib.sha256).hexdigest())
        sent=[]
        receiver=Relay(self.root/'receiver.sqlite3',self.secret,'fixture-token','fixture-chat',
                       lambda name,phone: sent.append((name,phone)) or 'sent')
        self.assertEqual(receiver.handle(body,timestamp,signature)[0],200)
        self.assertEqual(sent,[('Анна','+79991234567')])

    def test_booking_model_crosses_php_and_relay_and_requires_acknowledgment(self):
        self.assertEqual(self.run_php(TEST_VEHICLE='haval-buyout')[0], 502)
        code, result = self.run_php(TEST_VEHICLE='haval-buyout', TEST_ACK='haval-buyout')
        self.assertEqual((code, result['status']), (200, 'success'))
        capture = json.loads((self.root / 'capture.json').read_text())
        data = json.loads(capture['body'])
        self.assertEqual(data['vehicle'], 'haval-buyout')
        self.assertEqual(data['consent_version'], '2026-11-09')
        headers = dict(h.split(': ',1) for h in capture['headers'])
        sent = []
        receiver = Relay(self.root/'booking.sqlite3', self.secret, 'fixture-token', 'fixture-chat',
                         lambda *args: sent.append(args) or 'sent')
        response = receiver.handle(capture['body'].encode(), headers['X-Yotaxi-Timestamp'], headers['X-Yotaxi-Signature'])
        self.assertEqual(response, (200, {'status': 'success', 'vehicle': 'haval-buyout'}))
        self.assertEqual(sent, [('Анна', '+79991234567', 'haval-buyout')])

    def test_2053_endpoint_with_explicit_ip_keeps_hostname_for_tls(self):
        code, result = self.run_php(RELAY_URL='https://relay.example:2053/yotaxi/v1/leads', RELAY_IPV4='82.148.251.22')
        self.assertEqual((code, result['status']), (200, 'success'))
        capture=json.loads((self.root/'capture.json').read_text())
        self.assertEqual(capture['resolve'], ['relay.example:2053:82.148.251.22'])

    def test_timeout_and_rejection_do_not_claim_success(self):
        for mode in ['timeout','forbidden','error']:
            code, result=self.run_php(TEST_MODE=mode)
            self.assertEqual((code,result['status']),(502,'error'))
            self.assertNotIn(self.secret,json.dumps(result))

    def test_insecure_urls_and_invalid_secret_are_rejected(self):
        for url in ['http://relay.example/v1/leads','https://user:password@relay.example/v1/leads',
                    'https://relay.example/v1/leads?secret=x']:
            self.assertEqual(self.run_php(RELAY_URL=url)[0],503)
        self.assertEqual(self.run_php(RELAY_SECRET='')[0],503)
        self.assertEqual(self.run_php(RELAY_IPV4='127.0.0.1')[0],503)
        self.assertEqual(self.run_php(RELAY_URL='https://relay.example:444/v1/leads')[0],503)
        self.assertFalse((self.root/'capture.json').exists())


if __name__=='__main__':unittest.main()
