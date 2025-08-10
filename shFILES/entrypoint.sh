#!/bin/sh
set -e

APP_USER=appuser

# Ensure data/logs ownership for non-root runtime (needs root)
if [ "$(id -u)" = "0" ] && id "$APP_USER" >/dev/null 2>&1; then
  chown -R "$APP_USER":"$APP_USER" /app/data 2>/dev/null || true
  chown -R "$APP_USER":"$APP_USER" /app/logs 2>/dev/null || true
fi

if [ "$(id -u)" = "0" ] && command -v gosu >/dev/null 2>&1 && id "$APP_USER" >/dev/null 2>&1; then
  exec gosu "$APP_USER" uvicorn main:app --host 0.0.0.0 --port 8000
else
  exec uvicorn main:app --host 0.0.0.0 --port 8000
fi


