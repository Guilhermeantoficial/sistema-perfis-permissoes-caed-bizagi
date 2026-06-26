# Guia completo — Windows e VS Code

## 1. Pré-requisitos

Instale:

- Python 3.11 ou superior;
- Visual Studio Code;
- extensão “Python” da Microsoft;
- Git, quando for versionar o projeto.

Confirme no PowerShell:

```powershell
python --version
code --version
```

## 2. Criar a pasta de trabalho

Exemplo:

```powershell
cd $HOME\Downloads
mkdir Sistema-Perfis-Permissoes
cd Sistema-Perfis-Permissoes
```

Extraia o conteúdo do ZIP para essa pasta.

## 3. Abrir no VS Code

```powershell
code .
```

## 4. Preparar automaticamente

No terminal integrado do VS Code:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
```

O script cria `.venv`, instala dependências, copia `.env.example` para `.env` e inicializa o banco.

## 5. Executar

```powershell
.\scripts\run_windows.bat
```

Abra:

```text
http://127.0.0.1:8000
```


## 6. Criar um processo sem documentação

1. Acesse a página inicial.
2. Clique em **Novo processo**.
3. Informe código e nome.
4. Responsável, descrição e documento de referência são opcionais.
5. Clique em **Criar processo**.
6. Na matriz, clique em **Adicionar perfil**.
7. Preencha hierarquia, perfil e tipo de agente.
8. Marque as permissões ou use um atalho.
9. Clique em **Salvar**.

O campo de referência pode permanecer vazio. Isso não bloqueia aprovação, exportação ou integração.

## 7. Encerrar

No terminal, pressione `Ctrl + C`.

## 8. Executar novamente

```powershell
.\scripts\run_windows.bat
```

## 9. Rodar testes

```powershell
.\.venv\Scripts\Activate.ps1
pytest -q
```

## 10. Restaurar o banco local

Pare o sistema e remova:

```powershell
Remove-Item .\data\app.db
python scripts\init_db.py
```

## 11. Configurar Bizagi

1. Copie as credenciais do ambiente de homologação.
2. Abra `.env` no VS Code.
3. Preencha URL, Client ID, Client Secret, GUID e XPaths.
4. Mantenha `BIZAGI_ENABLED=false` durante os testes de payload.
5. Use “Visualizar payload” e “Simular integração”.
6. Após aprovação técnica, altere para `BIZAGI_ENABLED=true`.
7. Reinicie o servidor.

## 12. Versionar no Git

```powershell
git init
git add .
git commit -m "feat: sistema de perfis e permissoes"
```

A pasta `.venv`, o banco e o `.env` já estão no `.gitignore`.

## 13. Problemas comuns

### Python não encontrado

Reinstale o Python marcando “Add Python to PATH”.

### Execução de script bloqueada

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### Porta 8000 ocupada

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

### Banco travado

Encerre todas as instâncias do servidor antes de remover ou copiar `data/app.db`.
