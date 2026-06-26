# Execução local

## Opção A — Windows, VS Code e SQLite

Pré-requisitos:

- Python 3.12 ou superior;
- VS Code;
- Git opcional.

Passos:

```powershell
code .
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
.\scripts\run_windows.bat
```

O script cria `.venv`, instala as dependências, copia `.env.example`, aplica as migrações e cria os dados iniciais. O `run_windows.bat` inicia o servidor e o worker de integração.

Acessos:

- aplicação: `http://127.0.0.1:8000`;
- Swagger: `http://127.0.0.1:8000/docs`;
- prontidão: `http://127.0.0.1:8000/health/ready`.

## Opção B — Docker e PostgreSQL

```powershell
Copy-Item .env.local.docker.example .env.local.docker
$env:ENV_FILE=".env.local.docker"
docker compose --env-file .env.local.docker -f compose.yaml -f compose.local.yaml up --build
```

Serviços iniciados:

- PostgreSQL;
- job de migração;
- job de seed;
- aplicação web;
- worker de integração.

Para encerrar:

```powershell
docker compose -f compose.yaml -f compose.local.yaml down
```

Para remover também o banco local:

```powershell
docker compose -f compose.yaml -f compose.local.yaml down -v
```

## Testes locais

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
python scripts\check_release.py
```
