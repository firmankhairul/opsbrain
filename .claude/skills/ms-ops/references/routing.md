# Routing

Prompt clues per domain, and the precedence rules for prompts that match more
than one skill.

## Prompt clues

| Clues | Skill |
|---|---|
| EC2, ECS, EKS (control plane), RDS, S3, CloudWatch, Lambda, IAM, VPC, ALB, TGW, Route53, CloudFront, GuardDuty, Security Hub, Config | `ops-cloud` (aws) |
| Huawei ECS/OBS/CCE/CES/LTS, `hcloud`, Cloud Eye, Enterprise Router, HSS, SecMaster | `ops-cloud` (huawei) |
| Azure VM, AKS, NSG, VNet, App Service, `az`, Azure SQL, Key Vault, Front Door, Defender, Entra ID | `ops-cloud` (azure) |
| GCE, GKE, Cloud SQL, GCS, `gcloud`, Cloud Run, Cloud Functions, SCC | `ops-cloud` (gcp) |
| Alibaba ECS/OSS/RDS/SLB, `aliyun` | `ops-cloud` (alibaba) |
| cost, billing, spend, budget, RI, Savings Plans, rightsizing, FinOps | `ops-cloud` (finops) |
| pod, deployment, namespace, StatefulSet, Ingress, HPA, Karpenter, node group, kubectl, helm, kustomize, ArgoCD, Flux | `ops-platform` (kubernetes) |
| Terraform, OpenTofu, terragrunt, tfstate, plan/apply, module/provider | `ops-platform` (terraform) |
| pipeline, runner, CI/CD, GitLab, `.gitlab-ci.yml`, artifact, SAST/DAST | `ops-platform` (cicd) |
| Docker, docker-compose, Dockerfile, container OOM/exit code, image pull, bind mount | `ops-platform` (container) |
| Grafana, Loki, Tempo, Mimir, Prometheus, alerting, dashboard, LogQL, PromQL | `ops-platform` (observability) |
| systemd, journald, CPU/OOM/disk on a VM, `/var/log`, kernel, swap, load average | `ops-troubleshoot` (linux) |
| DNS resolution, TLS handshake, port/connectivity, routing path, mtr/traceroute, MTU | `ops-troubleshoot` (network) |
| MySQL, MariaDB, PostgreSQL, Redis — slow query, lock, replication, connections | `ops-troubleshoot` (database) |
| Fortinet, CrowdStrike, EDR, SIEM, WAF, certificate, vulnerability, CVE | `ops-security` |
| Odoo, ERP, odoo-bin, addon, module, model, XML-RPC, OWL | `ops-odoo` |
| MoP, MoM, incident report, RCA document, monthly report, laporan bulanan | `ops-report` |
| issue, task, todo, backlog, action item, follow-up, `kerjakan #N`, assign, triage | `ops-issue` |

## Precedence (apply top-down)

- **Kubernetes vs container:** pod/deployment/helm/kubectl → `ops-platform`
  kubernetes. Plain Docker/Compose without Kubernetes → `ops-platform`
  container.
- **Node symptoms:** CPU/OOM/disk on a Kubernetes node, Karpenter, node
  autoscaling → `ops-platform`. Same symptom on an ordinary VM →
  `ops-troubleshoot`.
- **Managed vs self-hosted database:** RDS/Aurora/Cloud SQL/ElastiCache →
  `ops-cloud` first; bring in `ops-troubleshoot` database for query/lock
  tuning. Engine on a VM → `ops-troubleshoot` directly.
- **Network vs security vs cloud:** firewall appliance (Fortinet) →
  `ops-security`. OS-level path (DNS, TLS handshake, port, route) →
  `ops-troubleshoot`. Cloud primitives (VPC, SG, Route53, ALB, TGW) →
  `ops-cloud`.

## Multi-domain incidents

1. Map the dependency chain (e.g. user → CloudFront → ALB → EKS → RDS).
2. Find the bottleneck layer from each component's metrics.
3. Delegate to the primary skill and pass the cross-domain context.
4. Triage severity P1–P4 per `docs/standards/` severity criteria, gather state
   in parallel, build a timeline from logs and metrics, give status at each
   phase. Once resolved, offer `ops-report` for the incident report.
