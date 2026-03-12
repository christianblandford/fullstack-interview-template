#!/usr/bin/env bash
set -e

trap 'kill 0' EXIT

echo "Starting API (FastAPI) on http://localhost:8000 ..."
(cd api && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &

echo "Starting UI (Vite) ..."
(cd ui && yarn serve) &

wait
