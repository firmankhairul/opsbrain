# Ops Documentation Schema

This schema defines how customer documentation is maintained across cloud, platform, and application domains.

## Customer Folder Layout

`<slug>` is lowercase kebab-case and identical to the `folder:` key in
`customer.yaml` and to the slug in `monthly-report/report-registry.yaml`.

```
<slug>/
  customer.yaml          # accounts, profiles, roles, github_project, sow: contract/<file>
  README.md              # optional, one screen: what this customer is, who to ask
  contract/              # SoW, quotation, renewal, SLA — `sow:` points here
  docs/                  # templates in template/customer/ (create_customer, doc_create_customer_doc)
    overview.md          #   core: accounts, regions, services, business context
    instances.md         #   core: compute and database inventory
    network.md           #   core: VPC, SG, load balancers, DNS, connectivity
    access.md            #   core: how Example MSP reaches the environment (never credentials)
    security.md          #   optional, when there is security tooling to describe
    kubernetes.md        #   optional
    odoo.md              #   optional (created automatically for an odoo provider)
    cicd.md              #   optional
    monitoring.md        #   optional: stack, alarm routing, noisy alarms
    backup-dr.md         #   optional: plans, restore tests, RPO/RTO
    contacts.md          #   optional: PICs and escalation path
    *.mmd / diagram/     #   diagrams
  tickets/               # legacy ticket files only; new work lives in GitHub Issues
  mop/                   # BAU MoPs, one per change, `parent:` to a runbook when one exists
  mom/
  incident_report/
  knowledge-base/        # how-to and lessons specific to this customer
  assessment/            # standalone analyses, including large findings exports
  reports/               # documents sent to the customer (weekly, patching, security recap)
    data/                #   raw exports behind those reports (csv, json)
  projects/<name>/       # sustained project work, kebab-case, no spaces (doc_create_project):
    README.md            #   brief, scope, stakeholders, phase table, umbrella issue
    timeline.md          #   phases, dates, MANDAYS (estimate, not Bobot kerja)
    tdd.md               #   Technical Design Document, approved before execution
    tracker.md           #   customer-facing progress per phase
    handover.md          #   BAST basis + internal handover to BAU
    mop/                 #   one FULL step-by-step MoP per phase (doc_create_project_mop)
  accounts/<name>/       # multi-account customers only
monthly-report/output/<slug>/<YYYY-MM>/   # monthly reports live here, not per-customer
```

**Not at the customer root.** Agent instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
`MEMORY.md`) belong at the repo root, never per customer; a `CHANGELOG.md` is `git log`; raw
data (csv, xlsx, json, images) goes under `reports/data/`, `assessment/` or the project that
produced it; folder names are kebab-case without spaces or brackets; a folder named like the
customer inside the customer folder is a mistake. `scripts/audit_customer_completeness.py`
lists what is out of place and where it belongs (informational, never blocking).

## Front matter (five fields)

Every document that is meant to be found again starts with this block, as the very first lines
(nothing, not even a comment, before the opening `---`). All fields are optional; the index
fills the gaps from the folder and the first heading.

```
---
type: docs | kb | mop | incident | assessment | project | report | runbook
summary: one sentence that says what the document is for
tags: [windows, upgrade]
applies_to: [aws]
parent: kb/runbooks/windows-2016-to-2022-upgrade.md
---
```

`parent` is for a MoP or document that builds on a runbook or an earlier MoP; it is how reuse
is recorded. `doc_index(customer)` builds the one-page index from these blocks, so there is no
index file to maintain. New documents from `doc_create_*` templates already carry the block;
older ones gain it when they are next touched.

## Verification stamp

Every core doc carries, in its first lines, when it was last checked against the real
environment and by what:

```
> Terakhir diverifikasi: YYYY-MM-DD (issue #N, live read-only)
```

The source is `live read-only` (checked against the account), `dokumen` (taken from a customer
document) or `perubahan` (written after a change was executed). Update the line, and only that
line, whenever the doc is checked again, even if nothing else changed. A commit date is not a
verification date: any edit moves it. `doc_audit_freshness` reads this line.

## Core Docs (preferred first)

- `overview.md`: account/profile scope, region baseline, service summary.
- `instances.md`: workloads, compute inventory, ownership hints.
- `network.md`: VPC/subnet/SG/routing/load-balancer connectivity.
- `access.md`: SSO/profile access, bastion/SSM, key auth paths.

## Multi-Account Customer Layout

For customers with multiple AWS accounts/profiles, group docs per profile:

```
<Customer>/
  docs/
    overview.md              # customer-level summary, account map
    access.md                 # SSO sessions, login method per profile
    <profile1>/               # per-account/per-profile docs
      overview.md
      instances.md
      network.md
      access.md
    <profile2>/
      overview.md
      instances.md
      network.md
      access.md
    ...
  knowledge-base/
  assessment/            # assessments & standalone analyses
  tickets/
  mop/
  incident_report/
  monthly-report/
    YYYY-MM/
```

Multi-account customers always use the <profile> subfolder pattern. Single-account customers use flat docs/.

**Multi-account customers in this repo:**
- acme-retail, example-c, acme-retail, acme-retail, acme-retail (and future: nabati, acme-retail)

## Extension Docs (domain-activated)

- `kubernetes.md`: clusters, namespaces, workloads, ingress, observability hooks.
- `cdn.md`: CloudFront distributions, WAF WebACLs, origin mapping, cache policies.
- `dns.md`: Route53 hosted zones, record counts, delegation sets.
- `storage.md`: S3 buckets, lifecycle policies, CloudFront origin mapping.
- `container-registry.md`: ECR repositories, cross-account pull config, image lifecycle.
- `cicd.md`: pipelines, runners, deploy flows, ECR push targets, rollback entry points.
- `security.md`: GuardDuty, SecurityHub, WAF summary, Control Tower, compliance posture (customer-level).
- `odoo.md`: application topology, addons, workers, DB/runtime dependencies.

## Mermaid Conventions

- Keep diagrams in `*.mmd` files, one domain flow per file.
- Prefer concise node names and explicit edge labels.
- Update diagrams when topology or critical runtime flow changes.

## No-Duplicate Rule (mandatory)

Before writing:

1. Search existing docs in `<Customer>/docs/`.
2. If relevant file exists, update it (upsert).
3. Create new files only when no canonical target exists.
4. For create-new operations, require explicit user approval.

## Document Routing Rules

- `Incident Report` files go to `<Customer>/incident_report/` and must include a status field (`Open` or `Resolved`).
- Change documents (MoP) go to `<slug>/mop/` — one document per change, covering approval and procedure.
- `MoP` and `MoM` files go to `<Customer>/mop/` or `<Customer>/mom/`.
- `Monthly Report` output goes to `<Customer>/monthly-report/YYYY-MM/`.
- `Daily Tickets` go to `<Customer>/tickets/`.
- `Knowledge Base` entries go to `<Customer>/knowledge-base/`.

## End-of-Session Docs Workflow

After each customer session:

1. Produce `Proposed Docs Update` with file targets.
2. Write changes only after user approval.
3. Record what changed and why in concise bullet points.
