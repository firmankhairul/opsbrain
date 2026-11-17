# Incident Report

Scope: the formal record of an incident or outage — timeline, root cause, impact, and follow-up — including customer-facing RCAs.

**Path:** `<slug>/incident_report/incident-YYYY-MM-DD-<slug>.md`
**Scaffold:** `doc_create_incident_report(customer, slug, severity="P3", dry_run=True)` → `dry_run=False`. `severity` is P1-P4. Renders `template/artifacts/incident_report.md`.

## Required content

ID, Title, Severity (P1-P4), Status (`Open` or `Resolved`), Timeline (detection → response → resolution), Root Cause, Impact Assessment, Action Items.

**Optional:** Contributing Factors, Lessons Learned, MTTD/MTTR, Related Incidents.

Severity criteria P1-P4 are defined in `docs/standards/ops-issue-format.md` ("Incident severity — P1 to P4").

## Mapping to the scaffold template

The template uses Example MSP section names; map the required content onto them rather than adding parallel sections:

| Required | Template section |
|---|---|
| Severity | `## Incident Assessment` |
| Timeline | `## Chronology` (+ `## Steps Troubleshooting`) |
| Root Cause | `## Root Cause` |
| Action Items / Lessons Learned | `## Improvement Propose` |
| Impact Assessment, Status | Add under `## Incident Description` (the template has no dedicated field) |

## Writing rules

- Scope the report to the incident. Unrelated hygiene findings go to a separate ticket or assessment.
- Customer-facing version: formal tone, timeline, before/after metrics, lessons learned. Verify every number in-account before sending.
- Use a Mermaid `sequenceDiagram` for the timeline when a diagram helps.

## Cross-references

- Link the remediation MoP in Action Items.
- If a MoP execution caused the incident, link both ways.
- The issue for the incident is created first (`issue_create`); the incident report is created from it (`doc_create_incident_report`) and linked from the issue.
