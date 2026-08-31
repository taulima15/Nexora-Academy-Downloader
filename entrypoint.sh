#!/usr/bin/env bash
set -euo pipefail

exec gunicorn \
  --bind "0.0.0.0:${PORT:-5001}" \
  --workers 1 \
  --threads 8 \
  --timeout 1800 \
  app:app
