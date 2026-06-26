"""Validações automatizadas antes de publicar uma release."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, env: dict[str, str] | None = None, stdout=None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True, env=env, stdout=stdout)


run([sys.executable, "-m", "compileall", "-q", "app", "alembic"])
run(["ruff", "check", "app", "tests"])
run([sys.executable, "-m", "pytest"])

for path in [
    ROOT / "compose.yaml",
    ROOT / "compose.local.yaml",
    ROOT / "compose.homolog.yaml",
    ROOT / "compose.production.yaml",
    *ROOT.glob(".github/**/*.yml"),
    *ROOT.glob("deploy/k8s/**/*.yaml"),
]:
    list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    print("YAML OK", path.relative_to(ROOT))

if shutil.which("node"):
    run(["node", "--check", "app/static/js/app.js"])
    run(["node", "--check", "app/static/js/shell.js"])

postgres_env = os.environ.copy()
postgres_env.update(
    {
        "APP_ENV": "test",
        "AUTH_MODE": "disabled",
        "DATABASE_URL": "postgresql+psycopg://app:password@db:5432/app",
        "SECRET_KEY": "release-check-secret-with-at-least-32-characters",
    }
)
with open(os.devnull, "w", encoding="utf-8") as devnull:
    run(["alembic", "upgrade", "head", "--sql"], env=postgres_env, stdout=devnull)

print("Release validada.")
