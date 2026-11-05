#!/usr/bin/env bash
# يشغّل SQL الإعداد الفعلي من src/sync.js على PostgreSQL حقيقي ثم يختبر السياسات.
# محلياً: ينشئ عنقوداً مؤقتاً. في CI: يستخدم خدمة postgres عبر PGHOST/PGUSER/PGPASSWORD.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY' > /tmp/lm_setup.sql
import re, pathlib
s = pathlib.Path('src/sync.js').read_text()
print(s.split('const SETUP_SQL = `', 1)[1].split('`;', 1)[0])
PY
run_sql() { psql -X -q -v ON_ERROR_STOP=1 "$@" -f tests/sql_prelude.sql -f /tmp/lm_setup.sql -f tests/sql_policy_test.sql 2>&1 | sed -n '/PASS\|FAIL\|ERROR/p' | sed 's/^psql:[^:]*:[0-9]*: //'; return "${PIPESTATUS[0]}"; }
if [ -n "${PGHOST:-}" ]; then
  run_sql -d "${PGDATABASE:-postgres}"
  exit $?
fi
BIN=$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1)
DIR=$(mktemp -d); chmod 777 "$DIR"
AS=""; [ "$(id -u)" = 0 ] && AS="runuser -u postgres --"
$AS "$BIN/initdb" -D "$DIR/data" -U postgres -A trust >/dev/null
$AS "$BIN/pg_ctl" -D "$DIR/data" -o "-k $DIR -p 55432 -c listen_addresses=''" -l "$DIR/log" -w start >/dev/null
trap '$AS "$BIN/pg_ctl" -D "$DIR/data" -m immediate stop >/dev/null 2>&1; rm -rf "$DIR"' EXIT
set +e; run_sql -h "$DIR" -p 55432 -U postgres -d postgres; rc=$?; set -e
exit $rc
