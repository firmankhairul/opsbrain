---
name: ops-cloud
description: >-
  Operates managed customers' cloud accounts on AWS, Azure, GCP, Huawei Cloud, and Alibaba Cloud, plus cross-cloud cost analysis, with read-only checks by default and approved changes only. Use when the task mentions AWS, EC2, RDS, S3, VPC, IAM, Identity Center, CloudWatch, ELB/ALB, EKS, Lambda, Route 53, CloudFront, VPN, GuardDuty, Azure, VM, AKS, NSG, App Service, Key Vault, Front Door, GCP, GCE, GKE, Cloud SQL, Cloud Run, Pub/Sub, Huawei, ECS, OBS, CCE, Cloud Eye, Alibaba, Aliyun, OSS, SLB, ACK, AliDNS, or cost, billing, spend, budget, rightsizing, Savings Plan, Reserved Instance; or Indonesian ops words like cek, troubleshoot, scale, restart, biaya, tagihan, hemat on a cloud resource.
metadata:
  version: "4.0.0"
  replaces: "ops-aws ops-azure ops-gcp ops-huawei ops-alibaba ops-finops"
---

# Cloud Operations

Diagnose and change customer cloud resources on five providers, and analyze their cost, under ms-ops engagement rules.

## Engagement rules

- Enter through `ms-ops`: it resolves the customer, the profile, and reads `<slug>/docs/`. If this skill is invoked directly, call `get_customer` and read the customer docs before touching the account.
- Risk levels: **L1** read-only (Describe/List/Get, metrics, logs) runs without asking. **L2** scoped or reversible change needs a Change Proposal and explicit approval. **L3** destructive or wide blast radius needs an explicit warning, a Change Proposal, a Rollback Plan, and approval.
- Never guess a profile, account, subscription, or project. If ambiguous, ask one targeted question.
- Expired session: stop and return the exact login command; do not retry.
- Output contract: `Current State`, `Findings`, `Risk/Impact`, `Change Proposal`, `Rollback`, `Verification`, `Docs Delta` (drop proposal/rollback when read-only).

## Pick the reference

Read only the file you need.

| Provider / topic | Read | When |
|---|---|---|
| AWS | [aws.md](references/aws.md) | EC2, EBS, RDS, EKS, ELB, S3, VPN, Route 53, CloudFront, Lambda, IAM / Identity Center, Organizations/SCP, GuardDuty / Security Hub |
| Azure | [azure.md](references/azure.md) | VM, AKS, Azure SQL, App Service, Functions, Storage, VNet peering, Key Vault, Front Door, Defender / Sentinel / Entra ID |
| GCP | [gcp.md](references/gcp.md) | GCE, GKE, Cloud SQL, Cloud Run, Cloud Functions, LB / CDN, Pub/Sub, Cloud Armor, SCC |
| Huawei Cloud | [huawei.md](references/huawei.md) | ECS, RDS, CCE, ELB, OBS, LTS, VPN, DNS, NAT, HSS / SecMaster / CTS |
| Alibaba Cloud | [alibaba.md](references/alibaba.md) | ECS, RDS, ACK, SLB/ALB, OSS, AliDNS, RAM, Security Center, ActionTrail; AK/SK credential checks |
| Cost / FinOps | [finops.md](references/finops.md) | Spend breakdown, tag allocation, RI/SP/CUD coverage, rightsizing, waste, cost report |

Each provider file holds its playbooks, risk examples, golden-signal table, and session command.

## Common method

1. **Observe (L1):** gather current state with the provider CLI on the resolved profile/region. Cite doc URLs when a finding rests on documented behavior.
2. **Analyze:** correlate with `<slug>/docs/` (overview, instances, network, access). Name the anomaly or root cause.
3. **Propose (L2/L3):** Change Proposal with profile/scope, region, action, target, why, risk, rollback.
4. **Act:** only after explicit approval, exactly as proposed.
5. **Verify:** re-query the same resources; report before vs after. Record doc drift in `Docs Delta`.

Scope flags (pass on every call):

| Provider | CLI | Scope flags |
|---|---|---|
| AWS | `aws` | `--profile <name> --region <region>` |
| Azure | `az` | `--subscription <id>` (+ resource group from docs) |
| GCP | `gcloud`, `gsutil` | `--project <id>` |
| Huawei Cloud | `hcloud` | `--cli-profile <name> --region <region>` (default `ap-southeast-4`) |
| Alibaba Cloud | `aliyun` | `--profile <name>` + confirm `RegionId` |

Login commands (return these on an expired session):

| Provider | Command |
|---|---|
| AWS | `aws sso login --profile <name>` |
| Azure | `az login` |
| GCP | `gcloud auth login` |
| Huawei Cloud | `hcloud configure sso --cli-profile <name>` |
| Alibaba Cloud | `aliyun configure --profile <name>` (static AK/SK, no SSO) |

AWS tooling: AWS CLI with `--profile`/`--region`, or the `aws-core` plugin MCP (`aws___call_aws` / `aws___run_script`); docs via `aws___search_documentation`.

Cross-skill handoffs: pod/workload, Terraform, and CI issues go to `ops-platform`; in-guest OS, network-path, and database-engine issues go to `ops-troubleshoot`.

## Going deeper with plugins

Plugin skills own technique; this skill owns the engagement (customer, profile, risk level, what gets written down). Resolve the customer here first, then borrow the plugin.

- AWS depth: `aws-core:*` skills, e.g. `aws-core:aws-compute`, `aws-core:aws-networking`, `aws-core:aws-iam`, `aws-core:aws-database`, `aws-core:aws-observability`, `aws-core:aws-billing-and-cost-management`.
- Azure depth: `azure:*` plugin skills, only if that plugin is enabled.
- GCP depth: `gke-upgrades`, `gke-observability`, `google-cloud-waf-*` skills where installed.
