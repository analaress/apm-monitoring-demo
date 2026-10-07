# APM Demo API

Aplicação de demonstração para a atividade de APM. O endpoint `/checkout` possui parâmetros para provocar lentidão e falhas, permitindo observar o impacto em uma ferramenta de monitoramento.

## Executar com Docker

```bash
docker compose up --build
```

Serviços:

- API: http://localhost:8081
- Grafana: http://localhost:3000 (admin/admin na primeira execução)
- Jaeger: http://localhost:16686
- Prometheus: http://localhost:9090

## Roteiro de demonstração

```bash
curl http://localhost:8081/health
curl http://localhost:8081/produtos
curl "http://localhost:8081/checkout?delay_ms=80&external_ms=120"
curl "http://localhost:8081/checkout?delay_ms=100&external_ms=1800"
curl "http://localhost:8081/checkout?external_ms=1500&fail=true"
```

Compare o trace normal com o trace lento no Jaeger. O segundo mostra a dependência de pagamento como o gargalo. O terceiro demonstra uma falha de dependência externa com HTTP 504.

## Métricas

O endpoint `/metrics` expõe contagem por rota/status e histograma de duração para o Prometheus. No Grafana, use consultas como:

```promql
rate(http_requests_total[1m])
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```
