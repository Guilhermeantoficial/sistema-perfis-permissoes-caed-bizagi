# Validação da release 2.0

Validações executadas no pacote entregue:

- compilação dos módulos Python;
- lint Ruff sem erros;
- 12 testes automatizados aprovados;
- migração Alembic aplicada em banco SQLite limpo;
- SQL de migração gerado para o dialeto PostgreSQL;
- login local e sessão validados;
- CSRF válido e ausência de CSRF rejeitada;
- fluxo completo: criar, editar, enviar, revisar e aprovar;
- exportações JSON, CSV e DOCX;
- solicitação e aprovação de acesso;
- idempotência da outbox;
- mapeamento de autorização das rotas sensíveis;
- sintaxe dos arquivos JavaScript;
- parsing de todos os YAML de Compose, Kubernetes e GitHub Actions;
- OpenAPI gerado;
- inicialização real do Uvicorn em banco limpo, com migração automática;
- endpoints `/health/live`, `/health/ready` e página de login validados por HTTP.

Limitação do ambiente de geração: não havia Docker Engine disponível, portanto a imagem e o Compose não foram executados neste ambiente. Os arquivos foram validados sintaticamente; a construção da imagem também está configurada no workflow de CI e deve ser executada no repositório ou infraestrutura que possua Docker.

A auditoria online de vulnerabilidades com `pip-audit` depende de acesso ao índice de pacotes. O ambiente de geração não possuía conectividade DNS com o PyPI, portanto essa etapa não foi concluída localmente. O workflow de CI inclui `pip-audit` e deve executá-lo em uma infraestrutura com acesso à internet antes da promoção da imagem para homologação ou produção.
