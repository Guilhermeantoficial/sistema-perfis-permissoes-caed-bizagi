from __future__ import annotations

import os
from pathlib import Path

TEST_DB = Path('/tmp/caed_permissions_pytest.db')
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('AUTH_MODE', 'disabled')
os.environ.setdefault('DATABASE_URL', f'sqlite:///{TEST_DB}')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-with-at-least-32-characters')
os.environ.setdefault('RUN_MIGRATIONS_ON_STARTUP', 'true')
os.environ.setdefault('SEED_ON_STARTUP', 'true')
os.environ.setdefault('TRUSTED_HOSTS', 'testserver,localhost,127.0.0.1')
os.environ.setdefault('FORCE_HTTPS', 'false')
os.environ.setdefault('SESSION_HTTPS_ONLY', 'false')
os.environ.setdefault('BIZAGI_ENABLED', 'false')
os.environ.setdefault('N8N_ENABLED', 'false')
