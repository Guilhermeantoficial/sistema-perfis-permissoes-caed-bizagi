# Sistema de Perfis e Permissões CAEd · v2.0 Production Ready

Aplicação FastAPI para cadastrar processos, manter matrizes de perfis e permissões, solicitar acessos, aprovar versões em duas etapas e integrar configurações aprovadas ao Bizagi e ao n8n.

## O que está pronto

- interface CAEd responsiva, com todos os menus e páginas funcionais;
- login local para desenvolvimento e OpenID Connect para homologação/produção;
- autorização RBAC validada no back-end;
- solicitação e aprovação de acessos por papel ou permissão específica;
- PostgreSQL em homologação/produção e SQLite opcional no desenvolvimento direto;
- migrações Alembic;
- aprovação em duas etapas, auditoria e notificações;
- outbox persistente com idempotência, retentativas e worker separado;
- integração OAuth2/OData com Bizagi;
- webhooks n8n assinados por HMAC e callback idempotente;
- CSRF, headers de segurança, Trusted Hosts, HTTPS e cookies seguros;
- métricas Prometheus e logs JSON;
- Docker Compose, Kubernetes e GitHub Actions;
- testes automatizados e exportações JSON, CSV e DOCX.

## Início rápido no Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
.\scripts\run_windows.bat
```

Acesse `http://127.0.0.1:8000`.

Credencial local inicial, definida em `.env`:

- e-mail: `guilhermeantoniooficial@gmail.com`
- senha: `TroqueEstaSenha!123`

Troque a senha antes de usar a aplicação em uma máquina compartilhada. Login local é bloqueado por padrão fora de ambiente local.

## Início rápido com Docker e PostgreSQL

```powershell
Copy-Item .env.local.docker.example .env.local.docker
$env:ENV_FILE=".env.local.docker"
docker compose --env-file .env.local.docker -f compose.yaml -f compose.local.yaml up --build
```

Acesse `http://localhost:8000`.

## Ambientes

| Ambiente | Banco | Autenticação | HTTPS | Integrações |
|---|---|---|---|---|
| Local direto | SQLite | local | não | desabilitadas por padrão |
| Local Docker | PostgreSQL | local | não | desabilitadas por padrão |
| Homologação | PostgreSQL | OIDC | obrigatório | credenciais de HML |
| Produção | PostgreSQL gerenciado | OIDC | obrigatório | credenciais exclusivas de PROD |

## Publicação

1. copie o modelo de ambiente apropriado;
2. injete segredos por cofre, sem criar `.env` dentro da imagem;
3. execute `python -m app.cli check-config`;
4. execute a migração como job único: `alembic upgrade head`;
5. inicie a aplicação e pelo menos um worker;
6. valide `/health/live` e `/health/ready`;
7. libere o tráfego somente após o smoke test.

Consulte:

- [`docs/DEPLOY_LOCAL.md`](docs/DEPLOY_LOCAL.md)
- [`docs/DEPLOY_HOMOLOGACAO.md`](docs/DEPLOY_HOMOLOGACAO.md)
- [`docs/DEPLOY_PRODUCAO.md`](docs/DEPLOY_PRODUCAO.md)
- [`docs/SOLICITACOES_PARA_INFRAESTRUTURA.md`](docs/SOLICITACOES_PARA_INFRAESTRUTURA.md)
- [`docs/INTEGRACAO_BIZAGI_PRODUCAO.md`](docs/INTEGRACAO_BIZAGI_PRODUCAO.md)
- [`docs/OPERACAO_N8N.md`](docs/OPERACAO_N8N.md)
- [`docs/SEGURANCA_E_LGPD.md`](docs/SEGURANCA_E_LGPD.md)
- [`docs/RUNBOOK_OPERACIONAL.md`](docs/RUNBOOK_OPERACIONAL.md)

## Comandos administrativos

```bash
python -m app.cli check-config
python -m app.cli migrate
python -m app.cli seed
python -m app.cli generate-secret
python -m app.cli create-user --name "Nome" --email usuario@empresa.br --role Administrador
python -m app.cli export-openapi
```

## Componentes de execução

- `web`: interface e API FastAPI;
- `worker`: processamento assíncrono das integrações;
- `migrate`: aplicação controlada das migrações;
- `seed`: criação idempotente dos papéis, usuários e processo inicial;
- `db`: PostgreSQL apenas nos Compose de referência; em produção prefira serviço gerenciado;
- `proxy`: Nginx de referência para homologação/produção.

## Regra essencial da integração

O processo somente é enviado ao Bizagi após a aprovação final. O envio é registrado em uma fila persistente e executado pelo worker, com chave idempotente, correlação e retentativas. Uma falha externa não perde a configuração aprovada.

## Testes

```bash
python -m pytest
python scripts/check_release.py
```

## Estrutura

```text
app/                 aplicação, regras, integrações e templates
alembic/             migrações do banco
deploy/nginx/        proxy reverso de referência
deploy/k8s/          manifests e overlays
docs/                implantação, segurança, operação e solicitações
scripts/             preparação e execução local
tests/               testes automatizados
compose*.yaml        execução por ambiente
.github/workflows/   CI e publicação de imagem
```
