.PHONY: install migrate seed run worker test lint check docker-local docker-down config-check

install:
	python -m pip install -r requirements.lock
	python -m pip install -r requirements-dev.txt

migrate:
	python -m app.cli migrate

seed:
	python -m app.cli seed

run:
	python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

worker:
	python -m app.worker

test:
	python -m pytest

lint:
	ruff check app tests

check:
	python scripts/check_release.py

config-check:
	python -m app.cli check-config

docker-local:
	cp -n .env.local.docker.example .env.local.docker || true
	ENV_FILE=.env.local.docker docker compose --env-file .env.local.docker -f compose.yaml -f compose.local.yaml up --build

docker-down:
	docker compose -f compose.yaml -f compose.local.yaml down
