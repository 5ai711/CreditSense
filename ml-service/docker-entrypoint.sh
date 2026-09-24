#!/bin/sh
# Seed the data volume with the model trained at image build time, once.
set -e
DATA_DIR="${ML_DATA_DIR:-/data}"
if [ ! -f "$DATA_DIR/registry.json" ] && [ -d /app/seed ]; then
  mkdir -p "$DATA_DIR"
  cp -r /app/seed/. "$DATA_DIR/"
fi
exec uvicorn creditsense_ml.api:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
