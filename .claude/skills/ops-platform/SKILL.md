---
name: ops-platform
description: >-
  Operates the platform layer for managed customers: Kubernetes workloads, Terraform IaC, GitLab CI/CD, standalone Docker/Compose hosts, and the Prometheus/Grafana/Loki/Tempo observability stack. Use when the task involves kubectl, pod, deployment, CrashLoopBackOff, OOMKilled, ingress, PVC, node NotReady, helm, ArgoCD, Karpenter, GitOps, terraform plan/apply, state, drift, OpenTofu, terragrunt, GitLab pipeline, job, runner, .gitlab-ci.yml, CI/CD variables, container registry, Docker, docker compose, container exit code or OOM, volume or container networking, Grafana, Loki, LogQL, Prometheus, PromQL, Mimir, Tempo, Alloy, alert rule, dashboard, or SLO.
metadata:
  version: "4.0.0"
  replaces: "ops-devops ops-cicd ops-container ops-observability"
---

# Platform Operations

Troubleshoot and change customer Kubernetes, Terraform, GitLab CI/CD, Docker, and observability stacks safely.

## Engagement rules

- Enter through `ms-ops`: it resolves the customer, the profile, and reads `<slug>/docs/`. If this skill is invoked directly, call `get_customer` and read the customer docs before touching the account.
- Risk levels: **L1** read-only (Describe/List/Get, metrics, logs) runs without asking. **L2** scoped or reversible change needs a Change Proposal and explicit approval. **L3** destructive or wide blast radius needs an explicit warning, a Change Proposal, a Rollback Plan, and approval.
- Never guess a profile, account, subscription, or project. If ambiguous, ask one targeted question.
- Expired session: stop and return the exact login command; do not retry.
- Output contract: `Current State`, `Findings`, `Risk/Impact`, `Change Proposal`, `Rollback`, `Verification`, `Docs Delta` (drop proposal/rollback when read-only).

## Pick the reference

Read only the file the task needs. Open a second one only when the problem crosses topics (e.g. a pipeline deploying to K8s).

| Topic | Read | When |
|---|---|---|
| Kubernetes | [kubernetes.md](references/kubernetes.md) | pod/deployment/service/ingress/PVC/node, kubectl, Helm, ArgoCD/GitOps, Karpenter/node autoscaling, pod security |
| Terraform | [terraform.md](references/terraform.md) | terraform/OpenTofu/terragrunt plan/apply, state, import, drift, backend migration |
| CI/CD | [cicd.md](references/cicd.md) | GitLab pipeline/job/runner, `.gitlab-ci.yml`, artifacts/cache, CI variables, environments, registry |
| Container | [container.md](references/container.md) | plain Docker / docker compose host with no Kubernetes: exit codes, OOM, networking, volumes |
| Observability | [observability.md](references/observability.md) | Grafana, Loki/LogQL, Prometheus/Mimir/PromQL, Tempo, Alloy, alert rules, dashboards, cloud-native monitoring |

Precedence when keywords overlap:
- pod, deployment, helm, kubectl, anything running in a cluster → kubernetes, even if it says "container OOM".
- Plain Docker/compose without K8s → container.
- Karpenter, node autoscaling, GitOps/ArgoCD → kubernetes.
- terraform, OpenTofu, terragrunt, state → terraform, even when the resources are K8s or cloud.
- GitLab runner on a Docker host failing at the Docker layer → start in cicd, then container.
- Metrics/logs used only as evidence for another topic → stay in that topic; open observability for queries or alert/dashboard work.

## Common method

1. **Observe (L1).** Gather evidence before theorizing: events, status, logs, `terraform plan`, job trace, `docker inspect`, metrics.
2. **Analyze.** Classify the cause (config vs code vs resources vs connectivity vs runtime). Test one suspect at a time.
3. **Propose (L2/L3).** Change Proposal with environment/cluster/project, exact action, impact, rollback. Attach the plan/diff output.
4. **Act.** Only after approval. Back up state, values, or data before mutating it.
5. **Verify.** Confirm health and no residual drift; watch trends (memory, error rate), not one sample.

Platform-wide safety rules:
- Check kube context and namespace before any kubectl: `kubectl config current-context`, then pass `-n <ns>` explicitly. Mismatch with customer docs → stop and ask.
- Always show the diff first: `terraform plan -out=<file>` before `apply`, `helm diff upgrade` or `helm template` before `helm upgrade`, `argocd app diff` before sync, `docker compose config` before `up -d`.
- L2: `kubectl rollout restart`, `kubectl scale`, `helm upgrade`/`rollback`, `argocd app sync`/`rollback`, non-destructive `terraform apply`, `terraform import`/`state mv`, job retry/cancel, runner pause, `docker restart`, `docker compose up -d`, alert rule/dashboard changes.
- L3: `kubectl delete`, `kubectl drain`, `terraform apply` with any destroy/replace, `terraform state rm`, `terraform init -migrate-state`, CI/CD variable (secret) changes, runner registration, global CI config, `docker rm -f`, `docker volume rm`, any `prune`, daemon.json edit + Docker restart, datasource deletion, retention/storage backend changes.
- State and data first: back up Terraform state before any state command; snapshot Docker volumes before `rm`/`prune`; save `helm get values` before upgrade.
- Never put secrets in Terraform state, CI YAML, compose files, or job logs.
- Prod change on a shared platform component (ingress controller, CNI, Karpenter, runner fleet, Loki/Mimir) counts as L3 regardless of the command.

## Going deeper with plugins

Technique comes from plugins; engagement (customer, profile, risk gate, docs) stays here. Resolve the customer first, then borrow:

- `kubernetes-operations:gitops-workflow` — ArgoCD/Flux repo layout, sync strategy, progressive delivery.
- `kubernetes-operations:helm-chart-scaffolding` — building or restructuring Helm charts.
- `kubernetes-operations:k8s-manifest-generator` — writing Deployments, Services, ConfigMaps, etc.
- `kubernetes-operations:k8s-security-policies` — NetworkPolicy, Pod Security, RBAC design.
- Terraform: `terraform-style-guide` skill for HCL authoring; terraform plugin MCP for provider/module versions and docs (`get_latest_provider_version`, `get_provider_details`, `search_modules`). Its HCP run tools (`create_run`, etc.) are L2/L3 and follow the gate above.
- GitLab CI: `gitlab-ci-validator` skill to lint/audit `.gitlab-ci.yml`; gitlab MCP `validate_ci_lint` / `validate_project_ci_lint` for server-side lint.
- AWS-side context (EKS, CloudWatch, IAM for IRSA): AWS CLI with `--profile`, or the aws-core MCP / `aws-core:aws-containers`, `aws-core:aws-observability` skills.
