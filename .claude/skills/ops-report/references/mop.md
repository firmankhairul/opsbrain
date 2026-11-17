# MoP (Method of Procedure)

Scope: the single change document — one per change, covering both approval and execution.

**Path:** `<slug>/mop/MoP-YYYY-MM-DD-<slug>.md`
**Scaffold:** `doc_create_mop(customer, slug, dry_run=True)` → preview → `dry_run=False`. Renders `template/artifacts/mop.md`.

## When

Only when `ops-rules.md` rule 9 requires it: production with downtime or an OS/database/cluster upgrade, production and irreversible, or a formal customer approval of the window. Look for a parent runbook in `kb/runbooks/` first and set `parent:`; the same procedure on 3 or more hosts is one runbook plus a parameter table, not a MoP per host. Everything else is an action item in the issue (MoP-lite). The MoP is both the approval gate and the execution guide. The former separate Change Request was merged into the MoP on 2026-07-21; `cr/` no longer exists.

## Required sections

Status, Title, Author, Date, Customer, Environment, Executive Summary, Current State, Proposed Change, Risk Assessment (level, impact, blast radius), Schedule of Activity, Procedure (exact commands), Expected Result, Verification, Rollback Plan, Approval, Result.

**Optional:** Duration, Maintenance Window, Affected Services, Communication Plan.

Analysis that only justifies this change belongs in its *Current State* and *Risk Assessment* sections, not in a separate assessment.

## Status lifecycle

`proposed` → `approved` → `executed`, or `cancelled`.

A MoP written before anyone agreed to the change is simply `proposed` — a valid, complete state, not an unfinished document.

While the MoP is `proposed` or `approved`, `## Result` reads `*Pending execution — to be recorded upon completion.*` — never a bare heading or leftover template comments.

## Historical filenames

Documents issued as `CR-YYYY-MM-DD-*` keep that name inside `mop/`. Do not rename them — tickets from that period cite them by that name.

## MoP-specific checks

- Commands are copy-paste ready: correct profile, region, and resource IDs.
- Resource IDs match live infrastructure.
- Rollback steps verified as feasible.
- Sign-off block (Prepared / Reviewed / Approved By) and customer `.docx` export: [customer-delivery.md](customer-delivery.md).
- Use a Mermaid `gantt` for the execution timeline when a diagram helps.

## Cross-references

- Every MoP is linked from its ticket (the `Dokumen` row of the ticket's `## Environment`).
- A MoP that remediates an incident is linked from that incident report's Action Items.
- If executing the MoP causes an incident, link MoP and incident report both ways.
