# GCP playbooks

Scope: Google Cloud troubleshooting playbooks, risk examples, and golden signals via `gcloud` / `gsutil`. Pass `--project <id>` on every call.

## Risk examples

- **L1:** `list`, `describe`, `logging read`, `monitoring policies list`.
- **L2:** `instances start/stop/reset`, `firewall-rules update`, machine type change, node-pool resize/upgrade, Cloud SQL authorized network update, Cloud Run `minScale`.
- **L3:** `instances delete`, `sql instances delete`, `storage buckets delete`.

Change Proposal fields: Project, Action, Target, Why, Risk, Rollback.

## Instance unreachable
1. `gcloud compute instances describe` (RUNNING / STOPPED / TERMINATED).
2. `gcloud compute firewall-rules list` + `gcloud compute routes list`.
3. `gcloud compute instances get-serial-port-output` for boot issues.

## High resource utilization
1. Cloud Monitoring `compute.googleapis.com/instance/cpu/utilization`.
2. Check machine type vs workload. Correlate with Audit Logs.
3. Propose machine type change (L2).

## Cloud SQL connectivity
1. `gcloud sql instances describe` (status, IP, authorized networks).
2. Verify VPC peering or Cloud SQL Proxy.
3. Propose authorized network update (L2) or scaling (L2).

## GKE cluster issues
1. `gcloud container clusters describe` (status, version).
2. `gcloud container node-pools list` + `kubectl get nodes`.
3. Propose node-pool resize or upgrade (L2). For upgrade planning use the `gke-upgrades` skill.

## Load balancer
1. `gcloud compute backend-services get-health`: unhealthy backends.
2. `gcloud compute url-maps describe`: host/path routing.
3. `gcloud compute ssl-certificates describe`: expiry, managed cert status.
4. CDN: `cdnPolicy` on the backend service; `cdn/backend_request_count` for cache hit ratio.

## VPC peering
1. `gcloud compute networks peerings list`: `state` (ACTIVE / INACTIVE).
2. Verify `exportCustomRoutes` / `importCustomRoutes`.
3. Peered traffic is still subject to firewall rules; verify ingress for the peered CIDR.

## Cloud Functions
1. `gcloud functions logs read`: crash / timeout / OOM.
2. `gcloud functions describe`: `maxInstances`, `availableMemoryMb`, `timeout`.
3. Verify trigger type and IAM invoker permissions.

## Cloud Run
1. `gcloud run services describe`: traffic split across revisions.
2. Check `minScale` / `maxScale`, `containerConcurrency`.
3. Cold starts: propose `minScale=1` (L2). Verify `roles/run.invoker`.

## Cloud Monitoring and alerting
1. `gcloud alpha monitoring policies list`: enabled state, conditions.
2. `gcloud monitoring uptime list-configs`: targets, frequency.
3. MQL queries for custom metric analysis.

## Pub/Sub
1. `gcloud pubsub subscriptions describe`: backlog count.
2. Verify dead-letter topic config and DLQ count.
3. `subscription/oldest_unacked_message_age` for consumer lag.

## Cloud Armor
1. `gcloud compute security-policies describe`: rules, priorities.
2. Check rate-based ban rules and thresholds.
3. Review OWASP Top 10 preconfigured rules.

## Security posture
1. **SCC:** `gcloud scc findings list`, filter by severity.
2. **Audit Logs:** Admin + Data Access logs via the centralized sink.
3. **Org Policy:** check constraints (`requireOsLogin`, `restrictPublicIPs`, `disableServiceAccountKeyCreation`).

## Golden signals

| Signal | Metric | Threshold |
|---|---|---|
| Latency | `loadbalancing.googleapis.com/https/backend_latencies` p99 | < X ms |
| Errors | `loadbalancing.googleapis.com/https/request_count` 5xx | < X% |
| Saturation | `compute.googleapis.com/instance/cpu/utilization` | < 85% |
| Uptime | `monitoring.googleapis.com/uptime_check` | = 1 |

## Session
Expired: stop and return `gcloud auth login`.
