# Implantação em homologação

## Objetivo

Homologação deve reproduzir as características de produção: PostgreSQL, SSO/OIDC, HTTPS, worker, integrações separadas e segredos externos à imagem.

## Pré-requisitos

- DNS e certificado TLS;
- PostgreSQL exclusivo;
- aplicação OIDC de homologação;
- aplicação OAuth Bizagi de homologação;
- webhook n8n de homologação;
- acesso de rede entre aplicação, banco, provedor de identidade, n8n e Bizagi;
- cofre de segredos;
- registro de imagens Docker.

## Configuração

Use `.env.homolog.example` como inventário. Não copie credenciais reais para o Git.

Valide antes da implantação:

```bash
APP_ENV=homologation python -m app.cli check-config
```

## Docker Compose de referência

```bash
export ENV_FILE=/caminho/seguro/homolog.env
docker compose -f compose.yaml -f compose.homolog.yaml build
docker compose -f compose.yaml -f compose.homolog.yaml run --rm migrate
docker compose -f compose.yaml -f compose.homolog.yaml run --rm seed
docker compose -f compose.yaml -f compose.homolog.yaml up -d web worker proxy
docker compose -f compose.yaml -f compose.homolog.yaml ps
```

O proxy de referência publica a porta 8080. Em infraestrutura corporativa, o balanceador/WAF normalmente substitui esse proxy e encerra o TLS.

## Critérios de aceite

- login corporativo bem-sucedido;
- grupos OIDC convertidos nos papéis corretos;
- usuário sem permissão recebe 403 no back-end;
- criação e edição de processo;
- solicitação de acesso;
- revisão e aprovação final;
- worker consome eventos;
- n8n recebe assinatura válida;
- Bizagi inicia caso controlado;
- retorno do caso aparece na auditoria;
- backup e restauração do banco testados;
- logs possuem `request_id`, `correlation_id` e usuário;
- scanner de vulnerabilidade sem achado crítico.
