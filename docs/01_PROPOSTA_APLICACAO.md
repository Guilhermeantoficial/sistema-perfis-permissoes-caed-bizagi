# Proposta de aplicação — versão 1.6

## Objetivo

Centralizar a criação, configuração, aprovação e integração de matrizes de perfis e permissões. O sistema deve atender processos com ou sem documentação formal prévia.

## Princípio funcional

A documentação é uma referência opcional, não uma dependência. Um usuário pode criar um processo em branco, preencher a identificação, adicionar os perfis e definir as permissões diretamente na interface.

## Escopo entregue

1. Criação manual de processos pela página inicial.
2. Identificação editável: código, nome, responsável, referência e descrição.
3. Matriz de permissões com inclusão, duplicação e exclusão de perfis.
4. Filtro por perfil em componente `select`, agrupado por hierarquia.
5. Catálogo de ações: visualizar, registrar, editar, excluir, monitorar, aprovar e administrar.
6. Dependências de segurança automáticas.
7. Aprovação, bloqueio, reabertura e auditoria.
8. Exportação em JSON, CSV e DOCX.
9. Conector Bizagi isolado e configurável.
10. Interface institucional inspirada na identidade visual do CAEd.

## Benefícios

- elimina a obrigatoriedade de preparar um DOCX antes do cadastro;
- reduz retrabalho entre negócio, desenvolvimento e automação;
- mantém uma fonte única da versão aprovada;
- facilita a localização de perfis em matrizes extensas;
- preserva rastreabilidade e governança;
- prepara um contrato estável para o Bizagi.

## Evolução recomendada

- autenticação corporativa e SSO;
- perfis de acesso ao próprio sistema;
- comparação entre versões;
- importação opcional de DOCX ou planilha;
- aprovação em múltiplos níveis;
- dashboard de pendências;
- PostgreSQL, Alembic, logs estruturados e observabilidade.
