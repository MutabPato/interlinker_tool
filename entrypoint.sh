#!/bin/sh
set -eu

python manage.py migrate --noinput

if [ "${SKIP_COLLECTSTATIC:-0}" = "0" ]; then
  python manage.py collectstatic --noinput
fi

exec gunicorn interlinker_tool.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-30}"
