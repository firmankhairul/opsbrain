---
name: ops-report
description: >-
  Produces formal operational documents — MoP, MoM, incident report, assessment, weekly report — and the monthly customer report (markdown draft, then PPT). Use when the user explicitly asks for a MoP, MoM, incident report / RCA, change document, assessment, weekly report, or monthly report / laporan bulanan. Never on its own initiative.
metadata:
  version: "4.0.0"
  replaces: "ops-report ops-monthly-report"
---

# Operational Reports

Turn verified operational data into formal documents that serve as the single source of truth for a customer.

## Ground rules

- **Explicit request only.** Never create a report, MoP, or other document unless the user asks for it.
- **Customer-facing documents:** formal tone, no emoji, scope to what was asked (park unrelated findings separately), and verify every number in-account before sending.
- **Never fabricate.** Use `<TBD>` for unknowns; resource IDs must match live infrastructure.
- **Language:** artifacts are written in English unless the user asks otherwise.
- **Generated `.pptx` / `.docx` are never committed** — `.gitignore` blocks them; deliver from the working directory.
- **MoP only when ops-rules rule 9 says so, and never without looking for a parent.** Search `kb/runbooks/` and run `check_recurrence` first; set `parent:` in the MoP front matter. Per-instance problems go in the issue, not in a new MoP.
- **Issue first.** Verify the GitHub Issue exists (`issue_get` / `issue_find`) before creating any artifact; if not, create it first (`issue_create`, skill `ops-issue`). Link the document from the `Dokumen` row of the issue. Issue format: `docs/standards/ops-issue-format.md`.
- **Preview before write.** Every scaffold tool except `doc_create_monthly_report` defaults to `dry_run=True`: show the path and a content summary, get approval, then call with `dry_run=False`.

## Pick the reference

Never hand-write a skeleton. Each artifact has one template; the `scaffold_*`
tool renders it, then you fill it. All paths are relative to the repo root.

| Artifact | Template (source of truth) | Scaffold tool | Read | Output |
|---|---|---|---|---|
| Issue | `docs/standards/ops-issue-format.md` | `issue_create` | ops-issue-format | GitHub Issue (legacy ticket files: `<slug>/tickets/`) |
| Project package | `template/artifacts/project/` | `doc_create_project` (brief, timeline with mandays, TDD, tracker, handover/BAST) and `doc_create_project_mop` (one full MoP per phase) | SOP: Pekerjaan biasa vs proyek | `<slug>/projects/<name>/` |
| MoP (change) | `template/artifacts/mop.md` | `doc_create_mop` | [mop.md](references/mop.md) | `<slug>/mop/MoP-YYYY-MM-DD-<slug>.md` |
| Incident report / RCA | `template/artifacts/incident_report.md` | `doc_create_incident_report` | [incident-report.md](references/incident-report.md) | `<slug>/incident_report/incident-YYYY-MM-DD-<slug>.md` |
| MoM | `template/report-decks/mom-template.docx` (fallback `template/artifacts/mom.md`) | `doc_create_mom` | [mom.md](references/mom.md) | `<slug>/mom/MoM-YYYY-MM-DD-<slug>.docx` |
| Assessment | `template/artifacts/assessment.md` | `doc_create_assessment` | [assessment.md](references/assessment.md) | `<slug>/assessment/ASMT-YYYY-MM-DD-<slug>.md` |
| KB entry | `template/artifacts/kb.md` | `doc_create_kb_entry` | — | `<slug>/knowledge-base/KB-YYYY-MM-DD-<slug>.md` |
| Weekly report | per customer: `<slug>/reports/weekly/TEMPLATE-*.md` | none | [weekly-report.md](references/weekly-report.md) | `<slug>/reports/weekly/<YYYY-MM>/` |
| Monthly report (markdown) | [monthly-markdown-structure.md](references/monthly-markdown-structure.md) | `doc_create_monthly_report` (then move) | [monthly-report.md](references/monthly-report.md) | `monthly-report/output/<slug>/<YYYY-MM>/` |
| Monthly report (PPT) | `monthly-report/template/ICS_Compute_Deck_Template.pptx` (Example MSP Kit); custom: `monthly-report/custom/<slug>/` | `scripts/generate_ppt.py` | [monthly-ppt-conversion.md](references/monthly-ppt-conversion.md) | working dir only, never committed |
| SOW | `template/collateral/Template SOW Example MSP Compute.docx` (downloaded) | none | [customer-delivery.md](references/customer-delivery.md) | `<slug>/projects/<project>/SOW-YYYY-MM-DD-<slug>.docx` |
| Customer docs (onboarding) | `template/customer/` | `create_customer` | — | `<slug>/customer.yaml`, `<slug>/docs/*.md` |

To change a format, edit the template — never patch the format into this
skill. Client-facing `.docx` / `.pdf` of any artifact is rendered from its
`.md` by `scripts/build_report_docx.py` on the Example MSP letterhead — flow, SOW and
sign-off block in [customer-delivery.md](references/customer-delivery.md).

Classify by the nature of the work: change → MoP (one document for approval and procedure); incident/outage → incident report; meeting → MoM; standalone analysis with a verdict → assessment; scheduled weekly/monthly → the report types.

## Operating protocol

1. **Issue first** (see ground rules).
2. **Classify** the artifact with the table above.
3. **Reconnaissance:** read session findings and the customer's `<slug>/docs/` before drafting.
4. **Draft** from the scaffold skeleton; read only the reference for that artifact. Strip every template HTML comment (`<!-- ... -->`) and hint before presenting.
5. **Approve:** present the target path and a content summary before writing.
6. **Finalize:** write to the customer subfolder and link the artifact from the ticket (`Dokumen` row of `## Environment`).
7. **Customer export** (explicit request only): stage → sanitize with the native edit tool → `build_report_docx.py` → optional PDF, per [customer-delivery.md](references/customer-delivery.md).

Close every report turn with: **Target Path**, **Summary of Content**, **Sync Status** (docs drift — below).

## Documentation drift sync

1. **Identify drift:** compare session findings with the existing `<slug>/docs/`.
2. **Propose delta:** list the specific files and exact sections to update.
3. **Execute sync:** only after approval, update the canonical docs.
4. **No duplicates:** upsert into existing files; never create a parallel doc.

## Cross-references

- Ticket → MoP / incident report: every artifact is linked from its ticket.
- Incident → MoP: link the remediation MoP in the incident's Action Items.
- MoP → Incident: if a MoP execution causes an incident, link both ways.
- Monthly report → all: reference significant incidents and MoPs from the period.

## Diagrams

Mermaid only: `graph TD` for architecture, `sequenceDiagram` for incident timelines, `gantt` for MoP execution timelines.

## Quality checklist

- [ ] All required fields populated (no `<TBD>` in critical fields)
- [ ] Dates/timestamps consistent, timezone stated
- [ ] Resource IDs match live infrastructure
- [ ] MoP commands copy-paste ready (correct profile, region, IDs); rollback verified feasible
- [ ] Cross-references to related documents included
- [ ] Template HTML comments (`<!-- ... -->`) and hints stripped; pending sections stated (proposed MoP `## Result` → `*Pending execution — to be recorded upon completion.*`)
- [ ] No soft line break splits an inline code span
- [ ] Customer exports sanitized on the `/tmp/` copy with the native edit tool, never a regex script
- [ ] Spelling/grammar correct; technical terms consistent

## Monthly report quick path

1. Read `monthly-report/report-registry.yaml`; process only `enabled: true` customers and `include: true` accounts. Not in the registry → auto-add from `customer.yaml` (see reference). `report_template: custom` → read its `custom_data_collection` file first and keep its structure.
2. Credential preflight every included account with `aws sts get-caller-identity --profile <p>`; on failure give the registry `login_command` and stop that account. No partial report without explicit approval.
3. Fix inputs: `period_start`, exclusive `period_end`, `month_label`, profiles, regions (from the registry).
4. Create the skeleton at `monthly-report/output/<slug>/<YYYY-MM>/monthly-report-<slug>-<mon>-<year>.md` (scaffold writes elsewhere — move it).
5. Collect and write one section at a time, updating status markers (`TODO` → `In Progress` → `Done` / `Limited — reason`) after each.
6. Pull "Tickets This Period" from `<slug>/tickets/`.
7. Tell the user the draft is ready for review. Build the PPT only after they explicitly ask, from the verified `.md` with `python3 scripts/generate_ppt.py <slug> <YYYY-MM>` (customers with a polished previous-month deck: the `gen_ppt_final.py` method in monthly-ppt-conversion.md) — and render to PNG to look at it before delivery.

Full workflow, registry rules, and auth handling: [references/monthly-report.md](references/monthly-report.md).
