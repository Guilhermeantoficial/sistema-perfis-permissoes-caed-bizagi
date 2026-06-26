# Modelos para abertura de solicitações

## Solicitação à infraestrutura

**Assunto:** Provisionamento dos ambientes do Sistema de Perfis e Permissões CAEd

Solicitamos o provisionamento dos ambientes de homologação e produção para o Sistema de Perfis e Permissões CAEd, composto por aplicação FastAPI, worker de integrações e PostgreSQL.

Necessidades:

- domínio e HTTPS por ambiente;
- infraestrutura para contêineres web e worker;
- PostgreSQL com SSL, backup e restauração;
- cofre de segredos;
- logs, métricas e alertas;
- registro privado de imagens;
- conectividade com o provedor OIDC, Bizagi e n8n;
- health check em `/health/ready`;
- porta interna 8000;
- pipeline com aprovação entre homologação e produção.

Anexamos os inventários de variáveis `.env.homolog.example` e `.env.production.example` e o guia `SOLICITACOES_PARA_INFRAESTRUTURA.md`.

## Solicitação ao time de identidade

**Assunto:** Cadastro OIDC do Sistema de Perfis e Permissões CAEd

Solicitamos uma aplicação OIDC para cada ambiente, com:

- Redirect URI: `https://HOST/auth/callback`;
- claims: `sub`, `email`, `name`, `groups`;
- grupos para Administrador, Revisor, Aprovador, Auditor e Solicitante;
- Client ID, discovery URL e Client Secret por canal seguro;
- política de rotação de segredo;
- acesso restrito a usuários da organização.

## Solicitação ao time Bizagi

**Assunto:** Preparação da integração do Sistema de Perfis e Permissões com o Bizagi

Solicitamos, inicialmente em homologação:

- URL base e versão do Bizagi;
- aplicação OAuth2 Client Credentials com escopo API;
- usuário técnico dedicado e de privilégio mínimo;
- Client ID e Client Secret por canal seguro;
- GUID do processo publicado;
- lista dos XPaths do formulário inicial, tipos e obrigatoriedades;
- definição da estrutura para a coleção/matriz de perfis;
- campos para correlation ID e versão;
- formato da resposta e identificador do caso;
- regras de rede, proxy, certificado e allowlist;
- contato técnico e massa de teste.

O fluxo será: aprovação final na ferramenta → outbox/worker → OAuth2/OData Bizagi → criação de caso → persistência do identificador e auditoria.

## Solicitação ao time n8n

**Assunto:** Publicação do workflow n8n do Sistema de Perfis e Permissões

Solicitamos:

- webhook de produção por ambiente;
- secret HMAC distinto por ambiente;
- validação de timestamp, assinatura e event ID;
- notificações para revisão e aprovação;
- tratamento de erro e retentativas;
- callback assinado em `https://HOST/api/n8n/callback`;
- retenção e acesso aos logs de execução;
- responsável técnico pelo workflow.
