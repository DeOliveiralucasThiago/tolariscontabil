#!/usr/bin/env bash
# Sobe a API (porta interna 8000) e o site (porta $PORT). Se um dos dois cair, o container sai e a hospedagem reinicia.
set -u

alembic upgrade head || { echo "Falha nas migrações do banco; confira TOLARIS_DATABASE_URL." >&2; exit 1; }

uvicorn tolaris_api.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips='127.0.0.1' &
PID_API=$!

(cd web && HOSTNAME=0.0.0.0 PORT="${PORT:-10000}" exec node server.js) &
PID_WEB=$!

trap 'kill "$PID_API" "$PID_WEB" 2>/dev/null' TERM INT
wait -n "$PID_API" "$PID_WEB"
CODIGO=$?
kill "$PID_API" "$PID_WEB" 2>/dev/null
exit "$CODIGO"
