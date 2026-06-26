#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install -r requirements-dev.txt
[[ -f .env ]] || cp .env.example .env
python -m app.cli migrate
python -m app.cli seed
printf '\nPronto. Use ./scripts/run_linux.sh\n'
