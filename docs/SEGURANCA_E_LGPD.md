# Segurança, privacidade e LGPD

## Controles implementados

- autenticação OIDC em HML/PROD;
- Argon2 apenas para modo local;
- RBAC no servidor;
- concessões temporárias por processo;
- CSRF double-submit;
- cookies HttpOnly, SameSite e Secure por ambiente;
- CSP, HSTS, X-Frame-Options e demais headers;
- Trusted Hosts e CORS restritos;
- segredos via variáveis/cofre;
- auditoria de usuário, IP, request ID e detalhes;
- idempotência nas integrações;
- logs estruturados;
- aplicação em contêiner não-root e filesystem somente leitura.

## Decisões organizacionais pendentes

- prazo de retenção de auditoria;
- base legal e finalidade do tratamento;
- definição de controlador e operadores;
- procedimento para correção/exclusão de dados quando aplicável;
- classificação das informações;
- política de acesso de suporte;
- plano de resposta a incidentes;
- periodicidade de revisão dos acessos.

## Recomendação de mínimo privilégio

- Solicitante: cria, edita e envia os próprios processos;
- Revisor: revisa tecnicamente;
- Aprovador: decisão final e integração autorizada;
- Auditor: leitura e evidências;
- Administrador: usuários, papéis, parâmetros e fluxos.

A matriz de `app/authorization.py` é o padrão inicial. A página Papéis permite persistir um conjunto institucional de permissões.
