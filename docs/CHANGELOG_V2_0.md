# Changelog 2.0

## Segurança e autenticação

- OIDC corporativo;
- login local restrito ao desenvolvimento;
- Argon2;
- CSRF;
- RBAC no back-end;
- CSP, HSTS, Trusted Hosts e cookies seguros;
- execução não-root.

## Dados e confiabilidade

- PostgreSQL;
- migrações Alembic;
- controle otimista por `row_version`;
- UUID público e correlation ID;
- outbox persistente;
- idempotência e retentativas.

## Operação

- web e worker separados;
- health checks;
- métricas Prometheus;
- logs JSON;
- Docker Compose;
- Kubernetes;
- CI/CD.

## Funcional

- solicitação de acesso;
- aprovação de papel/permissões;
- concessões por processo;
- auditoria global;
- integração Bizagi assíncrona;
- n8n assinado por HMAC.
