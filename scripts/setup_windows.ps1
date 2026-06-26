$ErrorActionPreference = "Stop"

Write-Host "[1/6] Verificando Python 3.12+..." -ForegroundColor Cyan
python --version

if (-not (Test-Path ".venv")) {
  Write-Host "[2/6] Criando ambiente virtual .venv..." -ForegroundColor Cyan
  python -m venv .venv
} else {
  Write-Host "[2/6] Ambiente virtual ja existe." -ForegroundColor DarkGray
}

Write-Host "[3/6] Ativando ambiente virtual..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

Write-Host "[4/6] Instalando dependencias..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install -r requirements-dev.txt

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Arquivo .env criado. Troque a senha local antes de compartilhar a maquina." -ForegroundColor Yellow
}

Write-Host "[5/6] Aplicando migracoes..." -ForegroundColor Cyan
python -m app.cli migrate

Write-Host "[6/6] Criando dados iniciais..." -ForegroundColor Cyan
python -m app.cli seed

Write-Host "Pronto. Execute .\scripts\run_windows.bat" -ForegroundColor Green
