#!/bin/bash
cd "$(dirname "$0")"

./venv/bin/uvicorn telemetry_server:app --host 0.0.0.0 --port 8000 --no-access-log
