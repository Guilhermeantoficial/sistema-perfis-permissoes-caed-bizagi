@echo off
setlocal
if not exist .venv\Scripts\activate.bat (
  echo Ambiente virtual nao encontrado. Execute scripts\setup_windows.ps1 primeiro.
  exit /b 1
)
call .venv\Scripts\activate.bat
start "CAEd Worker" cmd /c "call .venv\Scripts\activate.bat && python -m app.worker"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
