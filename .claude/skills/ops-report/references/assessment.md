# Assessment

Scope: a standalone analysis with a conclusion — cost assessment, architecture review, feasibility study, security posture analysis.

**Path:** `<slug>/assessment/ASMT-YYYY-MM-DD-<slug>.md`
**Scaffold:** `doc_create_assessment(customer, slug, dry_run=True)` → `dry_run=False`. Renders `template/artifacts/assessment.md` (status `draft | review | final`).

## Does it belong here?

The test: could it be handed over on its own and still make sense? If yes, it is an assessment.

Not here:
- Analysis that only justifies one change → *Current State* + *Risk Assessment* in that MoP.
- Analysis that answers one ticket → *Investigation* in the ticket.
- Reusable findings → `knowledge-base/` (`doc_create_kb_entry`).
- Phased assessment engagements with deliverables → `projects/<name>/`.

## Required content

Verdict (conclusion first, before any evidence), Scope (included **and** excluded), Current State (dated, with verification source), Recommendation.

**Optional — delete what is unused:** Findings, Options Considered, Cost, Risks, Next Steps, Open Questions.

## Cost figures

Every cost figure must state its basis: on-demand list price, or actual after Savings Plans/RI. The gap can be ~50%; the ORS assessment overstated savings by 48% until corrected.
