#!/bin/sh
set -eu

case "${1:-web}" in
  migrate)
    exec alembic upgrade head
    ;;
  seed)
    exec python -m app.cli seed
    ;;
  worker)
    exec python -m app.worker
    ;;
  web)
    exec python -m uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
    ;;
  *)
    exec "$@"
    ;;
esac
