"""Add the relay route to the existing HTTPS :2053 virtual host, with rollback."""
from datetime import datetime, timezone
from pathlib import Path
import os
import re
import subprocess
import tempfile

CONFIG = Path('/etc/nginx/sites-enabled/vpn.mikhailnet.ru')
LIMITS = Path('/etc/nginx/conf.d/yotaxi-relay-limits.conf')
BACKUPS = Path('/root/yotaxi-relay-backups')
ZONE_TEXT = '''# Website lead relay only.
limit_req_zone $binary_remote_addr zone=yotaxi_relay_ip:1m rate=5r/s;
limit_conn_zone $binary_remote_addr zone=yotaxi_relay_conn:1m;
'''
LOCATION = '''
    # BEGIN YOTAXI RELAY
    location = /yotaxi/v1/leads {
        client_max_body_size 4k;
        client_body_timeout 5s;
        limit_req zone=yotaxi_relay_ip burst=10 nodelay;
        limit_req_status 429;
        limit_conn yotaxi_relay_conn 10;
        limit_except POST { deny all; }
        proxy_pass http://127.0.0.1:8031/v1/leads;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 3s;
        proxy_send_timeout 5s;
        proxy_read_timeout 18s;
        access_log off;
    }
    # END YOTAXI RELAY
'''


def write_config(path, content):
    stat = path.stat()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        temporary.chmod(stat.st_mode & 0o777)
        os.chown(temporary, stat.st_uid, stat.st_gid)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def configure(config=CONFIG, limits=LIMITS, backups=BACKUPS, runner=subprocess.run):
    config = config.resolve(strict=True)
    original = config.read_text()
    if len(re.findall(r'(?m)^\s*server\s*\{', original)) != 1:
        raise RuntimeError('Ожидался один server-блок. Ничего не изменено; сообщите в чат.')
    if not re.search(r'(?m)^\s*listen\s+2053\s+ssl\s*;', original):
        raise RuntimeError('Не найден ожидаемый HTTPS-порт 2053. Ничего не изменено.')
    if re.search(r'(?m)^\s*listen\s+(?:\S+:)?443\b', original):
        raise RuntimeError('В файле есть порт 443. Нужна дополнительная проверка; ничего не изменено.')
    marker = re.compile(r'(?m)^\s*server_name\s+vpn\.mikhailnet\.ru\s*;')
    matches = list(marker.finditer(original))
    if len(matches) != 1:
        raise RuntimeError('Не найден единственный ожидаемый server_name. Ничего не изменено.')
    if '/yotaxi/v1/leads' in original:
        raise RuntimeError('Маршрут уже существует. Повторно не добавляли; сообщите в чат.')
    if limits.exists():
        raise RuntimeError('Файл лимитов уже существует. Повторно не меняли; сообщите в чат.')
    runner(['nginx', '-t'], check=True)
    backups.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = backups / ('vpn-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '.conf')
    backup.write_text(original)
    backup.chmod(0o600)
    changed = original[:matches[0].end()] + '\n' + LOCATION + original[matches[0].end():]
    if config.read_text() != original:
        raise RuntimeError('Настройки изменились во время проверки; остановлено.')
    limits_created = False
    config_changed = False
    try:
        with limits.open('x') as file:
            limits_created = True
            file.write(ZONE_TEXT)
        limits.chmod(0o644)
        config_changed = True
        write_config(config, changed)
        runner(['nginx', '-t'], check=True)
        runner(['systemctl', 'reload', 'nginx'], check=True)
    except BaseException:
        if config_changed:
            write_config(config, original)
        if limits_created:
            limits.unlink()
        # A graceful nginx reload keeps the previous workers on validation errors.
        # Restore and reload the known baseline in case the reload itself failed.
        try:
            runner(['nginx', '-t'], check=True)
            runner(['systemctl', 'reload', 'nginx'], check=True)
        except Exception:
            print('Файлы восстановлены, но состояние nginx требует проверки.')
        raise
    print('HTTPS-маршрут добавлен. Резервная копия:', backup)


if __name__ == '__main__':
    try:
        configure()
    except Exception as exc:
        print('Настройка остановлена:', str(exc))
        raise SystemExit(1)
