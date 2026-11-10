# Комплекты публикации yotaxi.ru

**Для замены главной: `yotaxi-main-20261110.zip`.** Это новая версия сайта с SEO для https://yotaxi.ru/, папкой assets-v20261110 и robots/sitemap. Распаковать прямо в public_html с резервной копией старых трёх корневых файлов. Подробно: deploy/production/README.md. Предварительные booking-архивы ниже не заменяют главную.

# Цельный комплект для проверки мобильной версии

**Актуальный комплект: `booking-mobile-gallery-20261110.zip`** — отдельный просмотр автомобиля, галерея и преимущества в каталоге.

`booking-mobile-20261110.zip` — предыдущий комплект; он содержит только новую тестовую страницу и её CSS/JS/документы. Это цельный срез текущей версии, а не исходники из главной ветки main.

1. Загрузить ZIP в public_html SpaceWeb и распаковать прямо там.
2. Должны появиться public_html/booking-mobile.html и public_html/booking-mobile/.
3. Открыть https://yotaxi.ru/booking-mobile.html. Это отдельный адрес без старого кэша страницы и скриптов.

Существующие index.html, booking-preview.html, send.php, send-booking.php и приватные .env не заменяются. Используются имеющиеся фотографии в public_html и работающий send-booking.php. Документы остаются проектами до получения реквизитов оператора.

Сборка: `python3 scripts/build-preview-release.py`.
Проверка именно распакованного архива: `SITE_URL=http://127.0.0.1:8092/ PREVIEW_PAGE=booking-mobile.html node tests/mobile.browser.cjs`.
