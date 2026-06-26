# Regras de negócio — versão 1.6

## RN-01 — Criação independente

Um processo pode ser criado sem documento de origem. Código e nome são obrigatórios; responsável, descrição e referência são opcionais.

## RN-02 — Código único

O código identifica o processo e não pode se repetir na base.

## RN-03 — Matriz mínima

Para salvar a configuração, o processo deve possuir pelo menos um perfil.

## RN-04 — Unicidade do perfil

A combinação `hierarquia + nome do perfil` não pode se repetir no mesmo processo.

## RN-05 — Catálogo de permissões

- `VIEW`: visualizar;
- `REGISTER`: registrar;
- `EDIT`: editar;
- `DELETE`: excluir;
- `MONITOR`: monitorar;
- `APPROVE`: aprovar;
- `ADMINISTER`: administrar.

## RN-06 — Dependências

- registrar, editar, excluir, monitorar, aprovar ou administrar exigem visualizar;
- aprovar exige monitorar;
- administrar concede todo o catálogo.

## RN-07 — Resumo automático

O resumo textual é recalculado com base nas ações marcadas. Sem ações, o resumo será “Não se aplica”.

## RN-08 — Filtro de perfil

O filtro deve usar uma lista de seleção com a opção “Todos os perfis” e uma opção para cada perfil cadastrado. A lista é atualizada após inclusão, duplicação, alteração ou exclusão.

## RN-09 — Fluxo de status

- `draft`: edição liberada;
- `pending_approval`: edição bloqueada, aguardando decisão;
- `approved`: versão aprovada e bloqueada;
- `synced`: versão enviada ao Bizagi.

## RN-10 — Reabertura

Processos pendentes, aprovados ou sincronizados podem voltar a rascunho mediante ação auditada.

## RN-11 — Integração

Somente uma versão aprovada pode ser simulada ou sincronizada. A integração real exige configuração completa e `BIZAGI_ENABLED=true`.

## RN-12 — Auditoria

Devem gerar histórico: criação, salvamento, envio para aprovação, aprovação, reabertura, simulação e sincronização.

## RN-13 — Referência opcional por processo e perfil

O processo pode registrar um documento de referência. Cada perfil também pode informar uma fonte, como “Cadastro manual”, “Documento, p. 4” ou outra evidência.
