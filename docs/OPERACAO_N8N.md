# Operação do n8n

## Papel do n8n

O n8n é camada de orquestração. A aplicação continua sendo a fonte oficial das regras, aprovações e autorizações.

Eventos enviados:

- `approval.requested`;
- `approval.stage_completed`;
- `approval.approved`;
- `approval.rejected`;
- `bizagi.synced`;
- `integration.test`.

## Segurança

Cada requisição contém:

- `X-N8N-Timestamp`;
- `X-N8N-Signature: sha256=<hmac>`;
- `X-Event-ID`;
- `X-Idempotency-Key`.

A assinatura é HMAC-SHA256 de `<timestamp>.<body>` com `N8N_WEBHOOK_SECRET`. O workflow deve rejeitar timestamp antigo, assinatura inválida e event ID já processado.

O callback `/api/n8n/callback` usa a mesma validação e registra `WebhookReceipt` para impedir processamento repetido.

## Workflow sugerido

1. Webhook Production URL;
2. validação HMAC em Code node ou gateway;
3. Switch por `event`;
4. notificação por e-mail/Teams;
5. chamada HTTP opcional ao Bizagi;
6. tratamento de erro;
7. callback assinado para a aplicação;
8. persistência de event ID para idempotência.

O arquivo `docs/n8n_approval_workflow.example.json` pode ser usado como ponto de partida e precisa receber credenciais e validação HMAC antes de produção.
