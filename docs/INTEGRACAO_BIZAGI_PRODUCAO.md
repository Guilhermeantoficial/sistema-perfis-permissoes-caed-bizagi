# Integração Bizagi — checklist completo

## Informações a solicitar por ambiente

- URL base do Work Portal/projeto;
- versão do Bizagi;
- aplicação OAuth2 configurada com Client Credentials e escopo de API;
- Client ID e Client Secret;
- usuário técnico dedicado e de privilégio mínimo;
- GUID do processo publicado;
- XPaths exatos do formulário inicial;
- tipos, obrigatoriedade e limites dos campos;
- estrutura escolhida para a matriz: JSON, coleção ou entidade;
- campo de `correlation_id`;
- campo de versão;
- formato da resposta e identificador do caso;
- regras de firewall, proxy, certificado e allowlist;
- contato técnico e janela para testes.

## XPaths esperados pelo projeto

```text
BIZAGI_PAYLOAD_XPATH
BIZAGI_PROCESS_CODE_XPATH
BIZAGI_PROCESS_NAME_XPATH
BIZAGI_STATUS_XPATH
BIZAGI_CORRELATION_XPATH
BIZAGI_VERSION_XPATH
```

## Fluxo implementado

```text
Aprovação final
  → cria job idempotente na outbox
  → worker obtém token OAuth2
  → POST OData para iniciar o processo
  → registra case id, resposta, correlação e auditoria
  → falhas recebem backoff exponencial
  → após o limite, job fica failed para tratamento operacional
```

## Teste de homologação

1. configurar as variáveis Bizagi de HML;
2. executar `python -m app.cli check-config`;
3. iniciar web e worker;
4. criar e aprovar uma configuração de teste;
5. usar “Sincronizar com Bizagi” ou habilitar sincronização automática;
6. conferir o job na página Integrações;
7. localizar o caso no Bizagi pelo correlation ID;
8. comparar todos os campos e perfis;
9. repetir o comando e confirmar que a idempotency key impede duplicidade lógica;
10. testar erro de credencial e indisponibilidade temporária.

## Critérios de aceite

- token obtido sem conta administrativa;
- TLS validado;
- caso criado no processo correto;
- código, nome, versão e correlação íntegros;
- payload completo sem truncamento;
- case ID persistido;
- erro rastreável nos dois sistemas;
- retentativa sem perda;
- credenciais de HML e PROD distintas.
