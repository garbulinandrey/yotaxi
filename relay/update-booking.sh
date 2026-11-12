#!/bin/sh
# Run on the existing Austrian VPS as root, after reviewing this file.
set -eu
umask 077
cd /opt/yotaxi-relay
[ -f app.py ] && [ -f compose.yaml ] && [ -f tests/test_relay.py ]
update_dir=$(mktemp -d /tmp/yotaxi-booking.XXXXXX)
trap 'rm -rf "$update_dir"' EXIT HUP INT TERM
base=https://raw.githubusercontent.com/garbulinandrey/yotaxi/f7b19ff/relay
curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$base/app.py" -o "$update_dir/app.py"
curl --fail --silent --show-error --proto '=https' --tlsv1.2 "$base/tests/test_relay.py" -o "$update_dir/test_relay.py"
(cd "$update_dir" && printf '%s\n' '59c3b75434e28566b50fc6da8ebc330a6a48ecb20b20a41a9546a1cba8b848db  app.py' '61ebd73ce925e42515f7ec6994001bb3b3eec9fe01fef482d447429e3d505ac5  test_relay.py' | sha256sum -c -)
python3 -m py_compile "$update_dir/app.py" "$update_dir/test_relay.py"
docker compose config --quiet
backup_dir=$(mktemp -d /root/yotaxi-before-booking.XXXXXX)
cp -p app.py "$backup_dir/app.py"
cp -p tests/test_relay.py "$backup_dir/test_relay.py"
install -m 644 "$update_dir/app.py" app.py
install -m 644 "$update_dir/test_relay.py" tests/test_relay.py
docker compose build relay
docker compose run --rm --no-deps relay python -m unittest discover -s tests -p test_relay.py -v
# SQLite backup API gives a consistent snapshot while the old relay is running.
docker compose run --rm --no-deps relay python -c 'import sqlite3,time,os; p="/data/leads-before-booking-"+str(time.time_ns())+".sqlite3"; src=sqlite3.connect("file:/data/leads.sqlite3?mode=ro",uri=True); dst=sqlite3.connect(p); src.backup(dst); dst.close(); src.close(); os.chmod(p,0o600); print("Database backup:",p)'
docker compose up -d --no-deps relay
curl --fail --silent --show-error --retry 8 --retry-connrefused --retry-delay 1 --connect-timeout 5 --max-time 10 http://127.0.0.1:8031/health
printf '\nCode backup: %s\nRelay updated. Website files are a separate step.\n' "$backup_dir"
