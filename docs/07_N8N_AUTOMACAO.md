# Integração n8n — desenho de automação

## Objetivo

Usar o n8n como orquestrador de notificações e integrações, mantendo no sistema CAEd a fonte oficial das regras de negócio, estados e decisões.

## Arquitetura recomendada

```text
Sistema CAEd
  └─ evento de domínio
       └─ POST Webhook n8n
            ├─ validar evento e dados
            ├─ notificar responsável
            ├─ criar lembrete/SLA
            ├─ acionar API externa ou Bizagi
            └─ POST callback no Sistema CAEd
```

## Eventos de saída

| Evento | Quando ocorre | Uso recomendado |
|---|---|---|
| `approval.requested` | envio para aprovação | avisar revisor e criar prazo |
| `approval.stage_completed` | revisão concluída | avisar aprovador final |
| `approval.approved` | aprovação final | arquivar, comunicar e preparar Bizagi |
| `approval.rejected` | devolução para ajustes | avisar solicitante com justificativa |
| `bizagi.synced` | caso iniciado | informar número do caso e registrar evidência |
| `integration.test` | teste manual | validar conectividade e credenciais |

## Segurança

1. Configure Header Auth no Webhook do n8n.
2. Use o header `X-N8N-Webhook-Secret`.
3. Não grave o segredo no workflow exportado.
4. Mantenha `N8N_ENABLED=false` até a homologação.
5. Use HTTPS e limite o acesso de rede ao webhook.
6. No callback, envie o mesmo segredo no header.

## Callback

```http
POST /api/n8n/callback
Content-Type: application/json
X-N8N-Webhook-Secret: <segredo>
```

Exemplo:

```json
{
  "process_id": 1,
  "event": "notification.sent",
  "status": "completed",
  "message": "Notificação enviada ao revisor.",
  "actor": "n8n"
}
```

## Fluxo sugerido

1. Webhook recebe o evento.
2. Switch avalia `$json.event`.
3. Em `approval.requested`, envia mensagem ao revisor.
4. Registra um lembrete com Wait ou agenda externa.
5. Em `approval.approved`, chama o Bizagi ou apenas avisa que o payload está pronto.
6. Executa HTTP Request para o callback.
7. Se qualquer nó falhar, inicia um Error Workflow e notifica a equipe técnica.

## Desenvolvimento e produção

O Webhook do n8n possui URL de teste e URL de produção. Use a URL de teste enquanto o workflow estiver em desenvolvimento. Após ativá-lo, configure a URL de produção no `.env` da aplicação.
