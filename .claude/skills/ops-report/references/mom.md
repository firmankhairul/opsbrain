# MoM (Minutes of Meeting)

Scope: minutes of a customer or internal meeting, delivered as a Word document.

**Path:** `<slug>/mom/MoM-YYYY-MM-DD-<slug>.docx`
**Scaffold:** `doc_create_mom(customer, slug, dry_run=True)` → `dry_run=False`. On write it copies `template/report-decks/mom-template.docx`; if that file is missing it builds a plain python-docx document with the required headings. The dry-run preview renders `template/artifacts/mom.md` (markdown, Indonesian field labels).

## Required content

Date, Attendees, Agenda, Discussion Points, Action Items (owner + deadline), Next Meeting.

## Format

- Typography: Example MSP Brand Kit 2026 — headings **Instrument Sans**, body **Inter**, code **JetBrains Mono** (`docs/standards/ics-brand-guidelines.md`).
- Internal MoM: `doc_create_mom` copies `template/report-decks/mom-template.docx`. A client-facing copy on the Example MSP letterhead comes from `scripts/build_report_docx.py` — see [customer-delivery.md](customer-delivery.md).
- Fill the copied template in place; keep its layout and branding.
- The generated `.docx` is never committed (`.gitignore` blocks it); deliver it from the working directory.
- Action items with an owner on our side should also land as `- [ ]` items on the relevant ticket/issue (`issue_update_action_item`).
