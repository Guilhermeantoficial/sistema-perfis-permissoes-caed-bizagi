# Arquitetura técnica — versão 1.6

## Visão geral

A solução usa um monólito modular com interface server-side e API REST.

```text
Navegador
   │ HTML + CSS institucional + JavaScript
   ▼
FastAPI
   ├── criação e edição de processos
   ├── regras da matriz
   ├── aprovação, notificações e auditoria
   ├── exportação JSON/CSV/DOCX
   ├── adaptador Bizagi ── OAuth2 + OData ──► Bizagi
   └── adaptador n8n ── Webhook autenticado ──► n8n

FastAPI ── SQLAlchemy ── SQLite / PostgreSQL
```

## Componentes

- `app/main.py`: páginas e endpoints.
- `app/models.py`: entidades persistidas.
- `app/schemas.py`: contratos `ProcessCreate`, `MatrixUpdate` e validações.
- `app/services/process_service.py`: criação manual, unicidade, matriz e auditoria.
- `app/services/admin_service.py`: cadastros, notificações, aprovação e emissão de eventos.
- `app/services/export_service.py`: exportações.
- `app/integrations/bizagi.py`: autenticação e criação de caso.
- `app/integrations/n8n.py`: webhook, autenticação por header e tratamento de falhas.
- `app/templates`: páginas Jinja2.
- `app/static/css/app.css`: Enterprise Console.
- `app/static/js/shell.js`: menu, busca global, ajuda e notificações.
- `app/static/js/catalog.js`: filtros, modais e páginas administrativas.
- `app/static/js/index.js`: criação e filtragem de processos.
- `app/static/js/app.js`: editor, filtro e fluxo.

## Persistência

O desenvolvimento local utiliza SQLite. `DATABASE_URL` permite migrar para PostgreSQL. Para produção, recomenda-se Alembic para controle de versões do esquema.

## Segurança

O MVP usa o nome informado na interface como responsável funcional. Em produção, este valor deve vir da identidade autenticada, com autorização baseada em funções.

## API

- `/docs`: Swagger UI;
- `/redoc`: ReDoc;
- `/openapi.json`: contrato OpenAPI;
- `POST /api/processes`: criação manual;
- `PUT /api/processes/{id}/matrix`: atualização da identificação e matriz.
- `POST /api/processes/{id}/submit`: envio para a primeira etapa.
- `POST /api/processes/{id}/approve`: conclusão da etapa atual.
- `POST /api/n8n/callback`: retorno autenticado das automações.

## Desacoplamento documental

Nenhum serviço depende de leitura de DOCX. Documentos podem ser registrados como referência, importados futuramente ou ignorados sem alterar o fluxo operacional.
