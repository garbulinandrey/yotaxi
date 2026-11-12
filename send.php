<?php
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function respond(int $code, string $status, string $message = '', array $extra = []): void {
    http_response_code($code);
    echo json_encode(array_merge(['status' => $status, 'message' => $message], $extra), JSON_UNESCAPED_UNICODE);
    exit;
}

// Prefer process variables, then a private file outside the document root.
// The legacy location remains supported for existing hosting installations.
function setting(string $name): string {
    $value = getenv($name);
    if ($value !== false && $value !== '') return $value;
    foreach ([dirname(__DIR__) . '/.yotaxi.env', __DIR__ . '/.env'] as $path) {
        if (!is_readable($path)) continue;
        foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
            $line = trim($line);
            if ($line === '' || $line[0] === '#' || strpos($line, '=') === false) continue;
            [$key, $value] = explode('=', $line, 2);
            if (trim($key) === $name) return trim(trim($value), "\"'");
        }
    }
    return '';
}

// Share limits across workers. Do not trust client-supplied forwarding headers.
function allowRequest(): bool {
    $directory = sys_get_temp_dir() . '/yotaxi-' . substr(hash('sha256', __DIR__), 0, 16);
    if (!is_dir($directory) && !@mkdir($directory, 0700) && !is_dir($directory)) {
        respond(503, 'error', 'Отправка временно недоступна. Позвоните: +7 (927) 883-55-66.');
    }
    $file = @fopen($directory . '/requests.json', 'c+');
    if (!$file || !flock($file, LOCK_EX)) {
        respond(503, 'error', 'Отправка временно недоступна. Позвоните: +7 (927) 883-55-66.');
    }
    @chmod($directory . '/requests.json', 0600);
    $entries = json_decode(stream_get_contents($file), true);
    if (!is_array($entries)) $entries = [];
    $now = time();
    foreach ($entries as $key => $entry) {
        if (!is_array($entry) || ($entry['until'] ?? 0) <= $now) unset($entries[$key]);
    }
    $key = hash('sha256', $_SERVER['REMOTE_ADDR'] ?? 'unknown');
    $entry = $entries[$key] ?? ['until' => $now + 600, 'count' => 0];
    $allowed = $entry['count'] < 5 && (isset($entries[$key]) || count($entries) < 10000);
    if ($allowed) {
        $entry['count']++;
        $entries[$key] = $entry;
    }
    rewind($file);
    $encoded = json_encode($entries);
    $written = fwrite($file, $encoded);
    $saved = $written === strlen($encoded) && ftruncate($file, $written) && fflush($file);
    flock($file, LOCK_UN);
    fclose($file);
    if (!$saved) respond(503, 'error', 'Не удалось отправить заявку. Попробуйте позже.');
    return $allowed;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    respond(405, 'error', 'Используйте форму заявки.');
}
if ((int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > 8192) respond(413, 'error', 'Слишком большой запрос.');
foreach (['name', 'phone', 'website', 'vehicle', 'consent'] as $field) {
    if (isset($_POST[$field]) && !is_string($_POST[$field])) respond(422, 'error', 'Проверьте поля заявки.');
}
// Silently discard the hidden field filled by bots.
if (trim($_POST['website'] ?? '') !== '') respond(200, 'success', 'Заявка принята.');
$name = trim($_POST['name'] ?? '');
$phone = trim($_POST['phone'] ?? '');
$vehicle = trim($_POST['vehicle'] ?? '');
$vehicles = [
    'vesta-2019-21' => 'Lada Vesta 2019–2021 — аренда',
    'vesta-2023' => 'Lada Vesta NG 2023 — аренда',
    'solaris-manual' => 'Solaris МКПП — аренда',
    'solaris-auto' => 'Solaris АКПП — аренда',
    'jetta' => 'Jetta VA3 — аренда',
    'solaris-2024' => 'Solaris АКПП 2024 — аренда',
    'solaris-2025' => 'Solaris АКПП 2025 — аренда',
    'haval-rent' => 'Haval Jolion 2025 — аренда',
    'haval-buyout' => 'Haval Jolion 2025 — выкуп',
 ];
$consentVersion = '2026-11-09';
$errors = [];
if ($vehicle !== '' && !isset($vehicles[$vehicle])) $errors['vehicle'] = 'Выберите автомобиль из списка.';
if (($_POST['consent'] ?? '') !== $consentVersion) $errors['consent'] = 'Для отправки заявки необходимо согласие на обработку данных.';
if (!preg_match("/\A[\p{L}\p{M}][\p{L}\p{M} '\x{2019}-]{1,79}\z/u", $name)) {
    $errors['name'] = 'Введите имя: от 2 до 80 букв, можно с пробелом или дефисом.';
}
$digits = preg_replace('/[^0-9]/', '', $phone);
if (strlen($phone) > 40 || !preg_match('/\A\+?[0-9 ()-]+\z/', $phone) || !preg_match('/\A[78][0-9]{10}\z/', $digits)) {
    $errors['phone'] = 'Введите российский номер: +7 (999) 123-45-67 или 8 999 123-45-67.';
}
if ($errors) respond(422, 'error', 'Проверьте поля заявки.', ['errors' => $errors]);
$phone = '+7' . substr($digits, 1);
if (!allowRequest()) {
    header('Retry-After: 600');
    respond(429, 'error', 'Слишком много заявок. Попробуйте через 10 минут или позвоните: +7 (927) 883-55-66.');
}
// When configured, only the signed VPS relay is used; do not fall back to
// Telegram on a relay failure (it would reintroduce the blocked network route).
$relayUrl = setting('RELAY_URL');
if ($relayUrl !== '') {
    $secret = setting('RELAY_SECRET');
    $relayIPv4 = setting('RELAY_IPV4');
    $parts = parse_url($relayUrl);
    if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https'
        || empty($parts['host']) || isset($parts['user']) || isset($parts['pass'])
        || isset($parts['query']) || isset($parts['fragment'])
        || (isset($parts['port']) && !in_array($parts['port'], [443, 2053], true))
        || ($relayIPv4 !== '' && !filter_var($relayIPv4, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4 | FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE))
        || !preg_match('/\A[a-f0-9]{64}\z/', $secret) || !function_exists('curl_init')) {
        respond(503, 'error', 'Отправка временно недоступна. Позвоните: +7 (927) 883-55-66.');
    }
    $body = json_encode([
        'request_id' => bin2hex(random_bytes(16)), 'name' => $name, 'phone' => $phone,
        'vehicle' => $vehicle, 'consent_version' => $consentVersion
    ], JSON_UNESCAPED_UNICODE);
    $stamp = (string) time();
    $signature = hash_hmac('sha256', $stamp . "\n" . $body, $secret);
    $ch = curl_init($relayUrl);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $body,
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'X-Yotaxi-Timestamp: ' . $stamp,
            'X-Yotaxi-Signature: ' . $signature
        ],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_TIMEOUT => 15,
        CURLOPT_FOLLOWLOCATION => false,
    ]);
    if ($relayIPv4 !== '') {
        curl_setopt($ch, CURLOPT_RESOLVE, [
            $parts['host'] . ':' . ($parts['port'] ?? 443) . ':' . $relayIPv4
        ]);
    }
    $result = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    $response = is_string($result) ? json_decode($result, true) : null;
    if ($httpCode !== 200 || !is_array($response) || ($response['status'] ?? '') !== 'success'
        || ($vehicle !== '' && ($response['vehicle'] ?? '') !== $vehicle)) {
        respond(502, 'error', 'Не удалось подтвердить отправку. Позвоните: +7 (927) 883-55-66.');
    }
    respond(200, 'success', 'Спасибо! Заявка принята. Свяжемся с вами в рабочее время.');
}

$token = setting('TELEGRAM_TOKEN');
$chatId = setting('TELEGRAM_CHAT_ID');
if ($token === '' || $chatId === '' || !function_exists('curl_init')) {
    respond(503, 'error', 'Отправка временно недоступна. Позвоните: +7 (927) 883-55-66.');
}
$text = ($vehicle === '' ? "🔔 НОВАЯ ЗАЯВКА (Сайт)" : "🚗 БРОНИРОВАНИЕ (Сайт)\nАвтомобиль: " . $vehicles[$vehicle]) . "\n\n👤 Имя: {$name}\n📱 Телефон: {$phone}\nСогласие: {$consentVersion}";
$ch = curl_init('https://api.telegram.org/bot' . $token . '/sendMessage');
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => http_build_query(['chat_id' => $chatId, 'text' => $text]),
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_CONNECTTIMEOUT => 5,
    CURLOPT_TIMEOUT => 12,
    CURLOPT_FOLLOWLOCATION => false,
]);
$result = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);
$response = is_string($result) ? json_decode($result, true) : null;
if ($httpCode !== 200 || !is_array($response) || ($response['ok'] ?? false) !== true) {
    respond(502, 'error', 'Не удалось подтвердить отправку. Позвоните: +7 (927) 883-55-66.');
}
respond(200, 'success', 'Спасибо! Заявка принята. Свяжемся с вами в рабочее время.');
