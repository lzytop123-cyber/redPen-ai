#!/bin/sh
# 只监听本机 8001。不要改成 0.0.0.0，不要改成 8000。
set -eu
cd /opt/zxd-ai
export APP_ENV=production
exec /opt/zxd-ai/.venv/bin/uvicorn app.api.main:app \
  --host 127.0.0.1 \
  --port 8001 \
  --workers 1 \
  --proxy-headers \
  --forwarded-allow-ips=127.0.0.1
