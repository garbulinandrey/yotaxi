<?php
// ВАШИ НАСТРОЙКИ
$token = "7165974091:AAEA46oS4C1HH-P9b-8GFFpFmbwISq2AZ4A";
$chat_id = "-1002028265421";

// Проверяем, что пришли данные
if ($_SERVER["REQUEST_METHOD"] == "POST") {
    
    // Получаем данные из формы
    $name = htmlspecialchars($_POST['name']);
    $phone = htmlspecialchars($_POST['phone']);

    // Формируем красивое сообщение
    $txt = "<b>🔔 НОВАЯ ЗАЯВКА (Сайт)</b>%0A%0A";
    $txt .= "👤 <b>Имя:</b> " . $name . "%0A";
    $txt .= "📱 <b>Телефон:</b> " . $phone . "%0A";
    $txt .= "⏰ <b>Время:</b> " . date('d.m.Y H:i');

    // Ссылка для отправки
    $url = "https://api.telegram.org/bot{$token}/sendMessage?chat_id={$chat_id}&parse_mode=html&text={$txt}";
    
    // Отправляем через cURL (самый надежный способ)
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true); 
    $result = curl_exec($ch);
    curl_close($ch);

    // Говорим сайту, что все успешно
    echo json_encode(['status' => 'success']);
} else {
    echo json_encode(['status' => 'error']);
}
?>