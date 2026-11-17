---
name: ms-ops
description: >-
  Entry point for all customer operations in the ms-ops repo: resolves the
  customer and cloud profile, reads the customer's docs first, classifies the
  task, enforces the approval gate, then hands off to the right ops-* skill.
  Use when a prompt names a customer, account, IP, or service, or asks to
  check, cek, troubleshoot, scale, restart, fix, analyze, propose, report,
  cari, temukan, dimana, find, or search something in operations work.
metadata:
  version: "4.0.0"
---

# MS-Ops Router

Resolve who, where, and what kind of task — then delegate. Run every command
from the repo root. Full workflow rules live in `ops-rules.md`.

## Hard rules

1. **No mutation without explicit approval.** Read-only runs freely; any
   create/update/delete/restart/scale needs a bounded approved plan. Explicit
   YOLO/end-to-end approval follows `ops-rules.md` rules 4–5.
2. **No documents unless asked.** MoP/MoM/incident report/KB only on explicit
   request (tickets follow the workflow below).
3. **Never guess a profile or account.** Ambiguous → ask one targeted question.
4. **Assume logged in.** Use the profile directly; on expiry return the exact
   login command (table below) and stop.
5. **Lookups go through MCP first** (`search_docs`, `search_customer_kb`,
   `get_customer_by_ip`, `list_customer_docs`) before Grep/Read across the tree.
6. Artifacts are written in English; chat follows the user's language.

## Lifecycle

1. **Resolve the customer.** `get_customer(<name|profile|account id>)`, or
   `get_customer_by_ip` / `get_customer_by_account`. No match → ask: new contracted customer (`create_customer`) or a one-off
   request without a contract (customer `token`, `engagement=<client>`)? Never guess. Read-only accounts (e.g. acme-retail, most of acme-retail) are
   flagged in `customer.yaml`; never propose changes there.
2. **Classify.** `classify_task(<description>)`:
   - check / cek / list / status → proceed, no issue, no documents
   - anything else (incident, change, migrate, upgrade, terraform) → the work lives in
     a GitHub Issue: hand over to `ops-issue` (find the issue with `issue_find`, or
     create it with `issue_create`). A MoP or incident report is made only when an
     action item needs one.
   Use one combined preview/approval; routine writes covered by explicit approval
   run directly. Pause for changed targets/impact, extra mutations or failed verification.
3. **Docs first.** `doc_index(<customer>, query=<topic>)` (one-page index: titles,
   summaries, runbooks, MoP parents, verified dates) → open only what you need; read `overview`, `network`,
   `instances`, `access`; search `knowledge-base/` for the topic. Flag docs
   older than 30 days. Before opening an issue on a resource run
   `check_recurrence` and `issue_find`.
4. **Verify live** only for what the docs do not answer. Note drift.
5. **Delegate** to the skill below with the gathered context.
6. **Track.** Progress on action items via `issue_update_action_item`, never a
   free-form comment. Issue shape: `docs/standards/ops-issue-format.md`.
7. **Close out.** Summarize actions, list doc drift, propose doc updates
   (apply only after approval), propose a KB entry if the fix was non-obvious.

## Delegate

| Domain | Skill |
|---|---|
| AWS, Azure, GCP, Huawei, Alibaba resources; cost, billing, rightsizing | `ops-cloud` |
| Kubernetes, Terraform, Helm, ArgoCD, GitLab CI/CD, Docker/Compose, Grafana/Loki/Prometheus | `ops-platform` |
| VM/host (CPU, OOM, disk, systemd), DNS/TLS/port/routing, MySQL/PostgreSQL/Redis engine | `ops-troubleshoot` |
| Fortinet, CrowdStrike, WAF, certificates, CVE triage | `ops-security` |
| Odoo infra, app (XML-RPC), and custom module development | `ops-odoo` |
| MoP, MoM, incident report, monthly report (explicit request) | `ops-report` |
| File, assign, work or close a GitHub issue (`buat issue`, `assign`, `kerjakan #N`) | `ops-issue` |

Overlaps and prompt-clue tables: [references/routing.md](references/routing.md).
Repo layout, docs contract, and artifact paths:
[references/workspace.md](references/workspace.md).

## Plugin skills

`ops-*` skills own the engagement (customer, profile, approval gate,
artifacts). Plugin skills own technique. Enter here, resolve the customer,
then borrow depth: `aws-core:*` (AWS services, IAM, networking, cost),
`kubernetes-operations:*`, `terraform-style-guide`, `gitlab-ci-validator`.
Never start customer work from a plugin skill.

## Login commands

| Platform | Command |
|---|---|
| AWS | `aws sso login --profile <name>` |
| Huawei | `hcloud configure sso --cli-profile <name>` |
| Azure | `az login` |
| GCP | `gcloud auth login` |

In non-interactive runs, fail with `CREDENTIALS_REQUIRED` instead of waiting.

## Output contract

Every specialist answer carries: `Current State`, `Findings`,
`Risk/Impact`, `Change Proposal`, `Rollback`, `Verification`, `Docs Delta`
(drop proposal/rollback when read-only).
