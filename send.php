<?php
// Функция для загрузки .env без внешних библиотек
function loadEnv($file) {
    if (!file_exists($file)) {
        echo json_encode(['status' => 'error', 'message' => '.env file not found']);
        exit;
    }
    $lines = file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        if (strpos(trim($line), '#') === 0) continue;
        list($name, $value) = explode('=', $line, 2);
        $name = trim($name);
        $value = trim($value);
        putenv("$name=$value");
        $_ENV[$name] = $value;
    }
}

// Загружаем .env (поместите файл .env в ту же директорию, что и send.php)
loadEnv(__DIR__ . '/.env');

// Получаем переменные
$token = getenv('TELEGRAM_TOKEN');
$chat_id = getenv('TELEGRAM_CHAT_ID');

// Проверяем, что переменные загружены
if (empty($token) || empty($chat_id)) {
    echo json_encode(['status' => 'error', 'message' => 'Missing credentials from .env']);
    exit;
}

// Проверяем, что пришли данные
if ($_SERVER["REQUEST_METHOD"] == "POST") {
   
    // Получаем данные из формы
    $name = htmlspecialchars($_POST['name']);
    $phone = htmlspecialchars($_POST['phone']);
    
    // Формируем красивое сообщение
    $txt = "<b>🔔 НОВАЯ ЗАЯВКА (Сайт)</b>\n\n";
    $txt .= "👤 <b>Имя:</b> " . $name . "\n";
    $txt .= "📱 <b>Телефон:</b> " . $phone . "\n";
    $txt .= "⏰ <b>Время:</b> " . date('d.m.Y H:i') . "\n";
    
    // Проверяем наличие cURL
    if (!function_exists('curl_init')) {
        echo json_encode(['status' => 'error', 'message' => 'CURL not available']);
        exit;
    }
    
    // Ссылка для отправки с urlencode
    $url = "https://api.telegram.org/bot{$token}/sendMessage?chat_id={$chat_id}&parse_mode=html&text=" . urlencode($txt);
   
    // Отправляем через cURL
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    $result = curl_exec($ch);
    curl_close($ch);
    
    // Проверяем результат
    $result_json = json_decode($result, true);
    if ($result_json['ok']) {
        echo json_encode(['status' => 'success']);
    } else {
        echo json_encode(['status' => 'error', 'message' => $result_json['description'] ?? 'Unknown error']);
    }
} else {
    echo json_encode(['status' => 'error', 'message' => 'Invalid request method']);
}
?>