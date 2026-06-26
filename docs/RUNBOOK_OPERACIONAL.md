# Runbook operacional

## Verificação diária

- `/health/ready` responde 200;
- fila de integração sem jobs `failed`;
- banco com espaço e conexões normais;
- login OIDC disponível;
- certificados válidos;
- aprovações dentro do SLA.

## Job de integração falhou

1. abra Integrações e obtenha job, correlation ID e erro;
2. confirme status do n8n/Bizagi;
3. valide credencial e certificado;
4. não crie outro processo para contornar;
5. corrija a causa;
6. altere o job para `retrying` e `next_attempt_at=now` por procedimento administrativo controlado, ou use ferramenta operacional futura;
7. confirme conclusão e auditoria.

## Aplicação indisponível

1. consulte load balancer e pods/containers;
2. valide `/health/live` e `/health/ready` separadamente;
3. consulte logs pelo request ID;
4. confira PostgreSQL;
5. escale/reinicie somente após identificar o componente;
6. aplique rollback da imagem se a falha começou após release.

## Banco indisponível

- aplicação fica `degraded/not ready`;
- não force tráfego;
- worker deixa de consumir jobs sem perdê-los;
- acione DBA;
- após restauração, valide migração e consistência antes de reabrir.

## Rotação de secrets

- OIDC, Bizagi, n8n, SMTP e banco devem ter rotação separada;
- atualize o cofre;
- faça rolling restart;
- teste autenticação e integração;
- revogue o secret anterior após confirmar.
