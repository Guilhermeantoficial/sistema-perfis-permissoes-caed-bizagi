# Release 2.0.0 — Production Ready

Esta release transforma a versão funcional 1.6 em uma base de implantação corporativa.

## Entregas principais

- execução local direta e Docker;
- ambientes de homologação e produção;
- autenticação OIDC;
- RBAC de back-end;
- solicitação e aprovação de acesso;
- PostgreSQL e Alembic;
- outbox/worker com retentativa e idempotência;
- Bizagi OAuth2/OData;
- n8n com assinatura HMAC;
- CI/CD, Kubernetes, Nginx e health checks;
- métricas, logs estruturados e Sentry opcional;
- CSRF e headers de segurança;
- documentação e modelos para abertura de chamados.

## Compatibilidade

- Python 3.12+;
- PostgreSQL 15+ recomendado;
- navegadores corporativos modernos;
- Docker Compose v2 ou Kubernetes 1.27+ como referências de implantação.

## Observação

Os arquivos `.env.*.example` não possuem credenciais reais. A release só inicia em homologação/produção quando as configurações mínimas e os segredos reais forem fornecidos.
