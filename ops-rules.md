# Ops Workflow Rules

Source of truth for all AI agents in this project. Synced to: CLAUDE.md, AGENTS.md, GEMINI.md, .kiro/steering/.

---

## Workflow Classification

Before starting any task, classify it using the `classify_task` MCP tool or these rules:

| Type | Keywords | Artifacts Required |
|------|----------|--------------------|
| **check** | cek, check, list, show, get, monitor, status, health, ping, verify | None — proceed directly |
| **incident** | outage, down, error, gagal, fail, crash, unreachable, timeout, alert, offline | GitHub Issue; incident report only if an action item needs it |
| **change-low** | add, create, delete, remove, update, change, tambah, hapus, ubah, restart | GitHub Issue; MoP only per rule 9 |
| **change-high** | migrate, upgrade, replace, major, database, rds, eks, cluster, terraform | GitHub Issue; MoP per rule 9 (high risk) |

## Mandatory Rules

### 1. Always classify first
Use `classify_task(description)` or the keyword table above. Do not guess.

### 2. Checks require no artifacts
If type is `check`, proceed directly — no ticket, no MoP. Ask first if unclear.

### 3. All non-check tasks need an issue first
Use `issue_create(customer, title, symptom, impact, requester, dry_run=True)` to preview, get user approval, then `dry_run=False` to create (skill `ops-issue`, flow in `docs/guides/workflow.md`).

Never create a MoP or Incident Report without a linked issue: create it only when an action item needs it, and link it from the `Dokumen` row of the issue.

### 4. Approval gate before any mutating action
This includes: file creation, AWS/cloud API calls that write/change/delete, restarts, config changes.

**Do:** Propose the action → wait for user confirmation → execute.

Approval may cover one action or an explicit end-to-end plan. See **Execution mode** below.

### 5. dry_run=True is default on every tool that writes
Write tools retain `dry_run=True` defaults. In normal mode show a combined preview and obtain approval. Routine progress/evidence, docs and closure writes already included in an approved plan may run with `dry_run=False`; do not repeat per-tool previews or approval requests. Substantive body rewrites still require a preview and preservation checks.

#### Execution mode: normal or YOLO / end-to-end

- **Normal:** establish targets, proposed actions, impact, verification and rollback; preview the plan and wait for approval before mutation.
- **YOLO / end-to-end:** an explicit instruction such as “backup these two DBs, record configuration, terminate, update docs/tasks and close” approves that bounded sequence. Record the instruction/source once in the issue. Continue Get → Analyze → Ship → Done without asking again for included actions. “YOLO” alone with unclear targets or actions needs clarification.
- Verify identities, backup gates and results as usual. Pause for a new decision if targets/impact change, an extra mutation is needed, verification fails, or an external approval is required. An unmentioned snapshot cleanup, purchase or extra resource deletion needs its own approval.
- Closure must be explicitly included or separately requested. Record actual communication evidence (recipient/channel/date); an operator-directed closure must say so and must not claim an unsent customer email. Record outstanding customer communication as a follow-up, not as completed work.
- Send chat updates at meaningful milestones, blockers and completion. Report the result and evidence links rather than narrating reads, previews and routine writes.

### 6. Update status as work progresses
Start from `issue_next(N)`: it returns the stage (Get, Analyze, Ship, Done) and the one next step with its command, the same answer the banner's `Tahap` and `Next` lines carry. Analyze is one call, `issue_analyze` (owner, weight and scope, action items, banner, board). Record each step with `issue_update_action_item(issue, item, status, note)` (statuses `pending`, `in_progress`, `blocked`, `pending_approval`, `done`); it keeps the row, the banner and the evidence comment in step, and mirrors Status, Weight and Segment onto the board. `in_progress` and `done` are refused while `Bobot kerja` is still TBD (`force=True` passes and is recorded). Work done by Example MSP that waits for an approver is two rows: the work `Done`, and a separate approval row `Pending Approval`. Banner status over the life of an issue:
- Created → **Open** (board `Todo`; the customer's own board when `github_project:` is set, else the shared org board #60 with the Customer column)
- Working → **In Progress** (also when every row is done but the reply/Docs Delta are not)
- Waiting for an approver → **Pending Approval** (`status="pending_approval"`)
- Blocked by access or another team → **Escalated** (`status="blocked"`, `Bola di` names who)
- Fix verified + customer reply + Docs Delta → **Resolved** and closed, only via `issue_resolve`

An issue may be filed and analysed without an owner; `done` and `issue_resolve` refuse until `issue_assign` gave it one.

`ticket_file_update_status` is only for the legacy ticket files that already exist.

### 7. No mutating AWS/cloud actions without explicit approval
Always show the command/plan first. Use `check_sso_session(profile)` to verify session before acting.

### 8. GitHub Issue lifecycle
A GitHub Issue tracks the **operational work**, not the merge of its markdown. Keep them separate.

- **Issue = work status.** Close after execution, verification, communication and Docs Delta; explicit operator-directed closure follows rule 5 and records any communication follow-up truthfully.
- **Issue body = the state NOW.** Maintain the 5-block summary through targeted status/field updates; comments hold action evidence. Reserve `issue_rewrite_body` for structural cleanup or substantive replacement, not routine progress. Full format: **`docs/standards/ops-issue-format.md`**.
- **One issue = one story.** A change that comes out of an issue is a **new** issue with `Related: #N`. No sub-issues. A new incident on an old problem is a new issue: `Recurrence of #N`.
- **Commits/PRs use `Refs #N`, never `Closes #N`** — unless that merge itself completes the work. `Closes`/`Fixes` auto-close the issue on merge, which is wrong when the fix is not yet executed.
- **Docs, tickets, and MoPs go straight to `main`** (they are operational logs, not code). Open a PR only when review is explicitly wanted.
- **Progress goes through `issue_update_action_item`, never a free-form comment.** It posts the dated evidence comment (investigating → fix-proposed → executing → verified) for you. Long detail goes to a comment with `issue_move_detail_to_comment`.

**Standard order:** `issue_create` (Todo) → read the issue and the customer docs → `issue_analyze` (owner, weight and scope, action items; `issue_list(stage="Get")` finds the ones waiting) → verify each action item read-only → execute each with approval, `issue_update_action_item` after every step → `doc_create_mop` / `doc_create_incident_report` only if an action item needs one → verify, send the customer reply → `issue_resolve` (Docs Delta, Resolved, close). Skill `ops-issue`; walkthrough in `docs/guides/workflow.md`.

**Lean checkpoint:** call `issue_next` when picking up an issue, then read its current body/recent comments once. Reuse that context until a write, handover or concurrent change requires a refresh. `issue_get` defaults to recent bounded comments; request `include_history=True` only for a specific historical question. Record start, meaningful findings, blocker and verified completion—not every read/command. Use action updates for row/banner/evidence together; their board sync is sufficient. One final live check verifies closure and board. Read the writing standard only when composing or repairing the format, not again for each checkpoint.

**Legacy ticket files.** The 250-odd existing `<slug>/tickets/*.md` files stay. `ticket_file_update_status` and `ticket_file_sync_to_issue` still work on them. The tools that created new ticket files were retired on 2026-10-15: new work starts with `issue_create`. `ticket_file_sync_to_issue` derives the issue body from a ticket only when it creates the issue and leaves an existing issue's body and state alone.

**Issue body format and work weight are defined in `docs/standards/ops-issue-format.md`**
(mirrored to `.kiro/steering/ops-issue-format.md`). It covers the 5-block body, the
comment conventions, and the weight table used for capacity planning. Every issue body
carries a `> **Bobot kerja:** <n> — <reasoning>` line; the exact wording matters because
it is parsed.

### 9. MoP: when it is required

A MoP is not the default product of a change. Walk the list top-down and stop at the first match:

1. Check, report, assessment, cost analysis, incident diagnosis: **no MoP.**
2. Non-production and reversible: **no MoP.** Write a MoP-lite in the action item.
3. Production with downtime, restart, instance replacement, cutover, or an OS, database or cluster upgrade: **MoP required.**
4. Production and irreversible (deleting data, snapshots, volumes or accounts; encryption by restore; shrinking or resizing a volume; buying RI or Savings Plans; a Compliance-mode lock): **MoP required.**
5. The customer must formally approve the window or the impact: **MoP required.**
6. Production, reversible, no downtime, at most 3 steps (DNS, security group, tag, schedule, user access, rename, retention): **no MoP.** One line in `Catatan & keputusan` says why.
7. The same procedure on 3 or more hosts: **one parent MoP (a runbook in `kb/runbooks/`) plus a per-host parameter table.** A new MoP is created only when the procedure deviates, and it must set `parent:` to the runbook.
8. In doubt: start without a MoP and raise it to one the moment rule 3, 4 or 5 applies.

**Before creating any MoP** look for a parent: `kb/runbooks/` and `check_recurrence`. A MoP with no `parent:` is acceptable only when nothing similar exists.

**MoP-lite (no MoP file).** Keep the steps, the verification, the short rollback and the approval inside the Action cell of the action item, and put the evidence in the comment that `issue_update_action_item` posts. Do not add table columns. Example:
`Enable deletion protection on <db>. Verify: describe-db-instances DeletionProtection=true. Rollback: --no-deletion-protection. Approved <name> <date> | Example MSP | Done <date> (evidence: comment)`

---

## Workflow Flow

```
User request
│
├── classify_task(description)
│   └── type: check → proceed directly (no issue, no documents)
│
└── any other type → GitHub Issue (skill ops-issue)
    │
    ├── Get      issue_create(dry_run=True) → approval → dry_run=False; assign an owner
    ├── Analyze  read issue + docs → action items → verify each (read-only)
    ├── Ship     execute with approval → issue_update_action_item after each step
    │            (doc_create_mop / doc_create_incident_report only if an item needs one)
    └── Done     customer reply sent → banner Resolved → close
```

---

## MCP Tools Available

Connect to `ms-ops` MCP server. Key tools:

**Issue (GitHub), the main flow:**
- `issue_create(customer, title, symptom, impact, requester, dry_run)` — basic issue, 5-block body
- `issue_classify(number, type, env, priority?, scope?, scope_reason?)` — weight from the standard table, scope line + label (SoW customers only), board; one dated comment
- `issue_assign(number, login)` — owner; required before `done` / resolve
- `issue_resolve(number, reply_evidence, docs_delta, source)` — Docs Delta row + Resolved + RESOLUTION comment + close + board Done
- `issue_list(customer?, assignee?, idle_days?)` — `assignee="none"` = no owner; `idle_days=30` = stale
- `issue_get(number)` / `issue_find(title_query)` — read
- `issue_update_action_item(issue, item, status, note)` — progress: row + banner + evidence comment
- `issue_rewrite_body(number, body)` — bring a body into the 5-block shape (old body archived)
- `issue_move_detail_to_comment`, `issue_audit_format`, `issue_set_board_fields`

**Documents (default dry_run=True):**
- `doc_create_mop(customer, slug, dry_run)` — MoP: the single change document
- `doc_create_incident_report(customer, slug, severity, dry_run)` — Incident Report
- `doc_create_assessment`, `doc_create_kb_entry`, `doc_create_mom`, `doc_create_monthly_report`

**Classification and legacy ticket files:**
- `classify_task(description)` — task type and risk (`check` needs nothing)
- `ticket_file_update_status`, `ticket_file_sync_to_issue` — existing legacy ticket files only

**Customer Discovery:**
- `list_customers(provider?)` — all customers
- `get_customer(query)` — fuzzy lookup by name/profile/account_id
- `check_sso_session(profile)` — verify AWS SSO session

**Docs:**
- `read_customer_doc(customer, doc)` — read overview/instances/network/access
- `list_customer_tickets(customer, status?)` — list tickets
- `list_open_customer_incidents(customer?)` — open incidents
- `search_docs(query, doc_type?)` — cross-customer search

---

## Customer Workspace Contract

Every customer folder follows one shape. Required core exists for all; optional
folders appear only when that artifact type has actually been produced.

### Slug rule (no exceptions)

One customer, one identifier, spelled the same in three places:

```
<slug>/                                   folder name at the repo root
<slug>/customer.yaml  → folder: <slug>    manifest key
monthly-report/report-registry.yaml       → slug: <slug>
```

`<slug>` is lowercase kebab-case: `acme-retail`, `acme-retail`, `acme-retail`. Never
`acme-retail/`, never `bisnis.com/`, never a registry slug that differs from the
folder. A dot in a folder name breaks scripts; capitals make the same
customer look like two.

Company names keep their real spelling in `name:` and `display_name:` and in
prose — only the path is normalized.

| Path | Purpose |
|------|---------|
| `<customer>/customer.yaml` | Manifest: display_name, folder, name, providers[] (provider + accounts[] with id/profile/region/role/purpose). |
| `<customer>/docs/overview.md` | Account ID, profile, region, VPC CIDR, short description. |
| `<customer>/docs/instances.md` | EC2/VM list + per-instance detail (ID, type, IP, SG, volume, apps). |
| `<customer>/docs/network.md` | VPC, subnet, Security Group rules, EIP, routing. |
| `<customer>/docs/access.md` | Key pair, IAM role, SSM, bastion/jumphost, domain, access method. |

Topic-specific docs (e.g. `grafana.md`, `odoo.md`) may sit beside the four
standard files. No other naming inside `docs/`.

**One-off / non-managed engagements:** set `managed: false` in `customer.yaml`.
Such folders opt out of the core-docs contract (`audit_customer_completeness.py`
skips them) — use for project/token work that is not managed services.

### Optional — created on demand only

| Path | Holds | Naming |
|------|-------|--------|
| `<customer>/tickets/` | Work tickets (ID `TKT-YYYY-MM-DD-<slug>` inside) | `YYYY-MM-DD-<slug>.md` |
| `<customer>/mop/` | Changes: approval + procedure | `MoP-YYYY-MM-DD-<slug>.md` |
| `<customer>/incident_report/` | Incident Reports | `incident-YYYY-MM-DD-<slug>.md` |
| `<customer>/mom/` | Minutes of Meeting | `MoM-YYYY-MM-DD-<slug>.docx` |
| `<customer>/knowledge-base/` | Customer-specific KB | `KB-YYYY-MM-DD-<slug>.md` |
| `<customer>/assessment/` | Assessments & analyses | `ASMT-YYYY-MM-DD-<slug>.md` |
| `<customer>/projects/<name>/` | Project work | kebab-case, no spaces |
| `<customer>/infra/<name>/` | IaC for this customer, usually a submodule | repo/stack name |
| `<customer>/` (whole folder) | May itself be a submodule for high-volume customers (e.g. `acme-retail/` → `acme-retail-ms`) — see `.kiro/steering/customer-submodules.md` | — |
| `<customer>/docs/<account>/` | Per-account facts, multi-account customers | account or profile name |
| `<customer>/accounts/<name>/` | Legacy per-account layout — see below | account or profile name |

Monthly reports do **not** live under the customer folder — they belong in
`monthly-report/output/<slug>/<YYYY-MM>/`. See below.

Do not create empty optional folders. Secrets (`key/`, `*.ppk`, `*.pem`,
`pwd.txt`, credential bundles) must be git-ignored and are never part of the
required contract.

### `assessment/` — where analysis lives

Assessment is a kind of work delivered, not just an activity, so it gets its
own folder rather than being scattered.

Goes in `assessment/`:

- Standalone analysis with a conclusion — cost assessment, architecture
  review, migration feasibility, security posture analysis
- Work the customer asked for as an assessment

Stays where it is:

- Analysis that only justifies one change → the MoP's **Current State** and
  **Risk Assessment** sections
- Analysis answering one ticket → the ticket's **Investigation** section
- A finding worth reusing later → `knowledge-base/`
- A multi-phase assessment engagement with its own deliverables →
  `projects/<name>/` (acme-retail's Cloud Environment Assessment runs this way)

The test: could this analysis be handed over on its own and still make
sense? Then `assessment/`. If it only means anything attached to a specific
change or ticket, keep it there.

Before this rule, analysis lived in six different places across six
customers — a dedicated folder, loose at the customer root, inside topic
folders, as a MoP, as a project, as a PoC.

### `projects/` versus the artifact folders

The artifact folders (`tickets/`, `mop/`, `incident_report/`, …) hold one document each,
named by date. `projects/` holds sustained work with its own internal
structure — an assessment, a migration, a workshop, a platform build.

```
acme-retail/projects/cloud-environment-assessment/
acme-retail/projects/bedrock-mantle-langfuse/
acme-retail/projects/erafos-rds-pg13-to-pg14/
```

Kebab-case, no spaces — a space in a path is a recurring source of script
bugs. If a project produces a formal MoP or CR, that document still goes in
the customer's `mop/`; the project folder keeps the working
material.

`accounts/<name>/` is for customers whose accounts are managed distinctly
enough to warrant their own records (example-a, example-b). Each may carry its own
`mop/`, `projects/`, `tickets/`.

### Credentials never enter the repo

Access keys, secrets, and private keys do not belong in tracked files —
including as default values in scripts, HTML forms, or config samples. Once
committed, a credential must be treated as leaked: `git rm` does not remove
it from history. Rotate the key first, clean the repo second.

Access Key IDs appearing in audit output or incident findings are
identifiers, not credentials, and may stay.

## Monthly Report Layout

`monthly-report/` is the report generator; one layout, no variants.

```
monthly-report/
├── report-registry.yaml         source of truth: which customers, which accounts
├── custom/<slug>/               per-customer collection recipes
├── template/Template.pptx       the deck template (input, not output)
├── output/<slug>/<YYYY-MM>/     generated reports — MARKDOWN ONLY
└── service-screener/
```

Rules:

1. Every directory under `output/` matches a registry slug.
2. `.pptx` and `.docx` are never committed — `.gitignore` blocks both.
   Generate, deliver, leave untracked.
3. No per-month flat dumps, no `<slug>/<YYYY-MM>/` at the `monthly-report/`
   root, no `<customer>/monthly-report/`. Those layouts existed once and were
   removed; do not recreate them.
4. `defaults.template_path` must point at a file that exists.

## Docs-First Gate

Before any account/cloud read for a customer, consult that customer's `docs/`
first (via `read_customer_doc` / `search_docs`). Go to the live account only
when: docs are missing, docs are stale for the question, or the task needs live
values docs cannot provide. When live findings contradict or extend the docs,
propose a docs update.

The same rule applies to the repo tree: `doc_index(<customer>, query=<topic>)`
comes before any Read/Grep/Glob under `<customer>/`. The index lists runbooks
(`kb/runbooks/`), MoP `parent:` links and summaries in one call, so a scaffold
MoP is recognised as "lengkapi parameter" rather than "MoP belum ada". Enforced
by `scripts/hooks/msops-docs-first-gate.py` (PreToolUse Read|Grep|Glob): it
denies until a marker `~/.cache/msops/docs-first/<slug>` is fresher than 8 hours.
The marker is written by `msops-docs-first-mark.py` after the MCP tool runs, or
by `scripts/doc_index.py <slug> "<topic>"` when the session's MCP server predates
the tool (restart Claude Code to reload it).

## Knowledge Base: Local vs Global

When a new condition or resolution arises that is worth reusing, propose
capturing it as a KB entry and route it:

- Customer-specific fact (this customer's env, quirk, one-off) →
  `<customer>/knowledge-base/KB-YYYY-MM-DD-<slug>.md`.
- Transferable technique (SOP, cross-customer pattern) →
  top-level `kb/KB-YYYY-MM-DD-<slug>.md`.

Ambiguity rule: if removing the customer name leaves the knowledge useful
elsewhere → global; otherwise → local.

---

## MoP: the single change document

There is one document per change, in `<customer>/mop/`. It carries both the
approval side (why, risk, sign-off, rollback) and the execution side
(procedure, verification, result).

`cr/` no longer exists. It was merged into `mop/` on 2026-07-21 — the two
had overlapping purposes and the rules governing them contradicted each
other: `ops-report` simultaneously said "every approved CR has a
corresponding MoP" and "MoP is not the default for every change". Actual
practice was 11 MoPs against 22 CRs, so the 1:1 rule was already fiction.
The MoP template had also drifted into doing the CR's job — its executive
summary read "to get formal approval for the plan, schedule, and impact".

**Status field** drives the lifecycle, replacing the old two-document dance:

| Status | Meaning |
|---|---|
| `proposed` | Written, not yet approved. A procedure documented for a change nobody has agreed to yet. |
| `approved` | Signed off, not yet executed. |
| `executed` | Done. Fill in the Result section. |
| `cancelled` | Superseded or abandoned. Say why. |

**Historical filenames are preserved.** Documents issued as `CR-YYYY-MM-DD-*`
keep that name inside `mop/`. They were CRs when they were written, and
tickets from that period reference them by that name; renaming them would
make those records point at something that never existed. New documents use
`MoP-YYYY-MM-DD-<slug>.md`.
