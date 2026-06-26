# Implantação em produção

## Topologia recomendada

```text
Usuário → DNS/WAF/Load Balancer HTTPS → web FastAPI → PostgreSQL
                                            │
                                            └→ outbox → workers → n8n/Bizagi/SMTP
```

O banco e o cofre de segredos devem ser serviços corporativos gerenciados. Execute pelo menos duas réplicas web e duas de worker quando houver requisito de alta disponibilidade.

## Sequência de release

1. aprovar a versão em homologação;
2. gerar imagem imutável com tag do commit;
3. executar testes, análise de dependências e scanner da imagem;
4. gerar backup do banco;
5. aplicar `alembic upgrade head` em job único;
6. publicar workers;
7. publicar web sem liberar tráfego;
8. validar `/health/live` e `/health/ready`;
9. fazer smoke test autenticado;
10. liberar tráfego gradualmente;
11. acompanhar erros, latência, filas e integrações;
12. registrar aceite e versão implantada.

## Comandos Compose de referência

```bash
export ENV_FILE=/run/secrets/production.env
docker compose -f compose.yaml -f compose.production.yaml pull
docker compose -f compose.yaml -f compose.production.yaml run --rm migrate
docker compose -f compose.yaml -f compose.production.yaml up -d web worker proxy
```

Para Kubernetes:

```bash
kubectl apply -k deploy/k8s/overlays/production
```

Antes de aplicar, substitua imagem, host, TLS e crie o Secret `caed-perfis-permissoes-secrets` pelo mecanismo oficial da plataforma.

## Rollback

- mantenha a imagem anterior disponível;
- não faça downgrade automático de banco sem script revisado;
- em falha de aplicação compatível com o schema, reverta a imagem;
- em migração destrutiva, restaure o backup e valide consistência;
- interrompa o worker durante restauração para impedir novos envios;
- eventos já concluídos possuem idempotency key e não devem ser reenviados manualmente sem análise.

## Go-live

- congelamento de alterações;
- aprovação do responsável funcional;
- equipe técnica em prontidão;
- canal de suporte divulgado;
- usuários e grupos provisionados;
- revisor e aprovador final configurados;
- primeiro processo real acompanhado ponta a ponta;
- relatório de estabilização após 24 e 72 horas.
