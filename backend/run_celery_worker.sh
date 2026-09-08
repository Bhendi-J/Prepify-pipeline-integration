#!/bin/zsh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

"$SCRIPT_DIR/venv/bin/celery" -A app.workers.celery_app:celery_app worker --loglevel=info
    