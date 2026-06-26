# Integração com Bizagi

## Objetivo

Após a aprovação, iniciar um caso no processo Bizagi e enviar a versão aprovada da matriz.

## Fluxo técnico

1. Validar que o status local é `approved`.
2. Gerar o payload de negócio.
3. Obter token OAuth 2.0 usando Client Credentials.
4. Enviar `POST` para o endpoint de início do processo.
5. Registrar requisição, resposta, caso criado e falhas.
6. Alterar o status local para `synced` quando houver sucesso.

## Endpoints usados pelo adaptador

```text
POST {BIZAGI_BASE_URL}/oauth2/server/token
POST {BIZAGI_BASE_URL}/odata/data/processes({BIZAGI_PROCESS_ID})/start
```

## Payload de início

O sistema produz o formato:

```json
{
  "startParameters": [
    {"xpath": "PerfisPermissoes.CodigoProcesso", "value": "2326"},
    {"xpath": "PerfisPermissoes.NomeProcesso", "value": "..."},
    {"xpath": "PerfisPermissoes.StatusAprovacao", "value": "approved"},
    {"xpath": "PerfisPermissoes.PayloadJson", "value": "{...}"}
  ]
}
```

## Por que usar JSON no primeiro ciclo

O documento ainda não define a entidade de coleção e os XPaths finais dentro do Bizagi. Enviar a matriz completa em um campo JSON mantém todos os dados e permite homologar o transporte antes de definir o mapeamento relacional definitivo.

## Itens necessários para homologação

- URL do Work Portal;
- Client ID e Client Secret de uma aplicação OAuth2;
- GUID do processo;
- XPaths do formulário inicial;
- usuário técnico vinculado à aplicação;
- ambiente de homologação;
- política de timeout, retry e tratamento de duplicidade.

## Idempotência

Antes de produção, recomenda-se incluir no Bizagi uma chave externa composta por `processo + versão`. O processo deve rejeitar ou reutilizar casos já criados para a mesma chave.

## Segurança operacional

- nunca versionar `.env`;
- usar cofre de segredos;
- restringir o usuário técnico ao menor privilégio;
- usar HTTPS e validar certificado;
- mascarar credenciais e dados sensíveis em logs;
- manter a integração desabilitada até aprovação de homologação.
