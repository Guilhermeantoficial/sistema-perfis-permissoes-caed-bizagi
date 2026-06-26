# Fluxo de aprovação

## Destino do botão “Enviar para aprovação”

O envio cria uma tarefa formal na página **Configurações > Fluxos de aprovação**.

Fluxo padrão:

1. **Revisão técnica** — responsável inicial: Marcos Costa.
2. **Aprovação final** — responsável inicial: Ana Ferreira.

Os responsáveis são configuráveis na própria página do fluxo e também podem ser definidos pelas variáveis:

```env
APPROVAL_DEFAULT_REVIEWER=Marcos Costa
APPROVAL_DEFAULT_FINAL_APPROVER=Ana Ferreira
```

## Regras

- O envio salva a matriz e muda o processo para `pending_approval`.
- A primeira aprovação conclui a revisão e cria a tarefa da etapa final.
- A aprovação final muda o processo para `approved` e bloqueia a matriz.
- A rejeição exige justificativa e devolve o processo para `draft`.
- A reabertura cancela solicitações pendentes e cria um novo ciclo de edição.
- Cada decisão gera auditoria e notificação interna.
- Quando o n8n está habilitado, cada transição também emite um evento de automação.
