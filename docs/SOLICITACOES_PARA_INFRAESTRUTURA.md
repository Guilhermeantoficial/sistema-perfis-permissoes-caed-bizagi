# O que solicitar para disponibilizar o sistema aos usuários

## 1. Infraestrutura

Solicitar:

- namespace, App Service, VM ou cluster para homologação e produção;
- registro privado para a imagem Docker;
- PostgreSQL 15+ com SSL, backup e restauração;
- DNS de homologação e produção;
- certificado TLS;
- WAF/load balancer/reverse proxy;
- cofre de segredos;
- centralização de logs e métricas;
- política de retenção e alertas;
- egress para OIDC, Bizagi e n8n;
- acesso administrativo restrito à equipe responsável.

## 2. Segurança e identidade

Solicitar ao time de identidade:

- duas aplicações OIDC, uma para HML e uma para PROD;
- redirect URI `https://HOST/auth/callback`;
- post logout URI `https://HOST/login`;
- claims `sub`, `email`, `name` e `groups`;
- grupos para Administrador, Revisor, Aprovador e Auditor;
- Client ID, discovery URL e Client Secret por canal seguro;
- política de rotação do secret;
- grupo padrão de usuários solicitantes.

## 3. Banco de dados

Solicitar:

- host, porta, database e usuário de aplicação;
- permissão DDL temporária/controlada para migrações ou usuário separado de migração;
- permissão DML para a aplicação;
- `sslmode=require` ou política equivalente;
- backup diário e retenção acordada;
- procedimento e prazo de restauração;
- monitoramento de conexões, espaço e queries lentas.

## 4. Bizagi

Use o checklist em `INTEGRACAO_BIZAGI_PRODUCAO.md`.

## 5. n8n

Solicitar:

- URL de webhook por ambiente;
- secret HMAC por ambiente;
- URL pública/privada de callback da aplicação;
- credenciais das ferramentas de notificação;
- política de retenção das execuções;
- responsáveis por manter e publicar o workflow.

## 6. Dados mínimos para abrir o chamado

```text
Sistema: Gestão de Perfis e Permissões CAEd
Ambientes: homologação e produção
Tecnologia: Docker / FastAPI / PostgreSQL
Porta interna: 8000
Health check: /health/ready
Callback OIDC: /auth/callback
Callback n8n: /api/n8n/callback
Dependências externas: Provedor OIDC, Bizagi, n8n, SMTP opcional
Dados sensíveis: credenciais técnicas, e-mail corporativo, matriz de acesso e trilha de auditoria
```
