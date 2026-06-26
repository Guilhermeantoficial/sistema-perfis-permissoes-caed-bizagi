# Matriz de papéis do sistema

| Permissão | Solicitante | Revisor | Aprovador | Auditor | Administrador |
|---|---:|---:|---:|---:|---:|
| Consultar processos | ✓ | ✓ | ✓ | ✓ | ✓ |
| Criar processo | ✓ |  |  |  | ✓ |
| Editar matriz | ✓ |  |  |  | ✓ |
| Enviar para aprovação | ✓ |  |  |  | ✓ |
| Aprovar/devolver |  | ✓ | ✓ |  | ✓ |
| Reabrir versão |  |  | ✓ |  | ✓ |
| Exportar | ✓ | ✓ | ✓ | ✓ | ✓ |
| Executar integração |  |  | ✓ |  | ✓ |
| Ver auditoria |  | ✓ | ✓ | ✓ | ✓ |
| Aprovar acesso |  |  | ✓ |  | ✓ |
| Gerir usuários/papéis/parâmetros |  |  |  |  | ✓ |

A autorização é verificada no middleware de back-end. Ocultar um menu não substitui a validação da rota.
