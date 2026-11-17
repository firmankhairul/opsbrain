# Observability playbooks

Scope: Grafana LGTM+P stack (Loki, Grafana, Tempo, Mimir/Prometheus, Pyroscope, Alloy) and cloud-native monitoring (CloudWatch, Azure Monitor, GCP Cloud Monitoring, Huawei Cloud Eye).

Risk mapping: dashboard viewing, log/metric queries, alert status = L1. Alert rule create/modify, dashboard updates, recording rules = L2. Datasource deletion, retention policy changes, storage backend migration = L3.

## LGTM+P component map

| Signal | Component | Query language |
|---|---|---|
| Logs | Loki | LogQL |
| Metrics | Mimir / Prometheus | PromQL |
| Traces | Tempo | TraceQL |
| Profiles | Pyroscope | FlameQL |
| Collection | Alloy (replaces Promtail/Agent) | River config |
| Visualization | Grafana | All above |

## Monitoring design: golden signals

Define all four for every service:

| Signal | What to measure | Example metric |
|---|---|---|
| Latency | Request duration | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))` |
| Traffic | Request rate | `rate(http_requests_total[5m])` |
| Errors | Error rate | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])` |
| Saturation | Resource usage | `container_memory_usage_bytes / container_spec_memory_limit_bytes` |

## LogQL patterns

```
# Error logs for an app
{app="myapp", env="prod"} |= "error" | logfmt | level="error"

# Rate of errors over time
rate({app="myapp"} |= "error" [5m])

# Top error messages
topk(10, sum by (msg) (count_over_time({app="myapp"} |= "error" | logfmt [1h])))

# Latency from access logs
{app="nginx"} | pattern `<_> - - <_> "<method> <path> <_>" <status> <_> <_> <latency>` | latency > 1s
```

## PromQL patterns

```
# CPU usage by pod
rate(container_cpu_usage_seconds_total{namespace="prod"}[5m])

# Memory usage %
container_memory_usage_bytes / container_spec_memory_limit_bytes * 100

# Request rate by service
sum(rate(http_requests_total[5m])) by (service)

# Error rate %
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# P99 latency
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

## Alerting rules
1. Alert on symptoms, not causes: "error rate > 5%", not "CPU > 80%".
2. Use a `for` duration of at least `5m` to avoid flapping.
3. Use multi-window burn rate for SLO-based alerts.
4. Severity levels: Critical (page), Warning (ticket), Info (dashboard).
5. Put a runbook link in every alert annotation.

## Correlation cheatsheet

| From → To | How |
|---|---|
| Logs → Traces | Derived field on traceID → Tempo datasource |
| Traces → Logs | Tempo "Logs" tab with Loki + `${__trace.traceId}` |
| Metrics → Traces | Exemplars on Prometheus/Mimir → Tempo |
| Traces → Profiles | `span.profileID` link → Pyroscope |

## Loki label design
- Good labels (low cardinality): `env`, `app`, `namespace`, `cluster`, `region`.
- Bad labels (high cardinality): `pod`, `request_id`, `user_id`, `trace_id`.
- Keep high-cardinality data in log lines; extract at query time with `logfmt`, `json`, `pattern`.

## Sizing guide

Loki:

| Scale | Mode |
|---|---|
| < 50 GB/day | Monolithic (1-3 nodes) |
| 50-500 GB/day | Simple Scalable (3-9 read/write/backend) |
| > 500 GB/day | Distributed (microservices, 15+) |

Mimir:

| Scale | Mode |
|---|---|
| < 1M active series | Single binary |
| 1-10M series | Simple Scalable |
| > 10M series | Distributed |

## Cloud-native monitoring

AWS CloudWatch (AWS CLI with `--profile`, or aws-core MCP):
- `aws cloudwatch get-metric-statistics` for EC2, RDS, ELB metrics.
- CloudWatch Logs Insights for log queries.
- CloudWatch Alarms → SNS for notifications.

Azure Monitor:
- `az monitor metrics list` for VM, SQL, App Service.
- Log Analytics KQL for deep investigation.
- Alert rules → Action Groups.

GCP Cloud Monitoring:
- MQL/PromQL for custom metrics.
- Uptime checks for endpoint monitoring.
- Alert policies → notification channels.

Huawei Cloud Eye:
- CES metrics for ECS, RDS, ELB.
- LTS for log queries.
- CES alarms for notifications.

## Core principles
1. Object storage for production; never filesystem for Loki/Mimir/Tempo.
2. Alloy over Promtail (Promtail is deprecated).
3. Use recording rules to pre-compute expensive PromQL.
4. Multi-tenancy from day one: send `X-Scope-OrgID` even for single-tenant.
5. OpenTelemetry for instrumentation.
