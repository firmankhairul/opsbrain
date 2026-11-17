# Weekly Report

Scope: recurring weekly operational reports (e.g. SOC weekly report) — a series with a fixed format week to week, not a one-off document.

There is no scaffold tool; layout and format rules are documented per customer.

## Data collection first — do not start by writing

Before creating or updating a weekly report for a customer:

1. Check whether the raw data export for the period exists (e.g. under `<slug>/reports/weekly/<YYYY-MM>/tickets/`). If not, **ask the user** where to get the data. Never invent it.
2. Check whether the period's narrative source (`<slug>/reports/weekly/<YYYY-MM>/*.md`) exists and is in sync with that data. If not, or if it looks out of date, **ask the user**. Do not assume an old draft still applies.

Only once both are clear, write or update the report.

## Per-customer layout

Technical details and format rules differ per customer, so they are documented locally:

```
<slug>/reports/weekly/
├── WORKFLOW.md        ← customer-specific workflow (required if the customer has its own docx pipeline)
├── TEMPLATE-*.md      ← narrative template, if the customer has one
├── <YYYY-MM>/
│   ├── <report>.md    ← narrative source, one file per week
│   ├── tickets/       ← raw data exports for the month
│   └── data/          ← structured data (e.g. JSON) for automated render
└── tools/             ← optional automated render (e.g. python-docx script + docx template)
```

If the customer has no `WORKFLOW.md`, write the weekly report as markdown following the agreed content standard (if any, under `<slug>/reports/reference/`). An automated docx pipeline is optional.

## Implementation reference

`example-e/reports/weekly/` has a full `WORKFLOW.md`, `TEMPLATE-mingguan.md`, and `tools/render_weekly_docx.py` (python-docx, consistent weekly style). Its content standard is `example-e/reports/reference/standar-laporan-mingguan-soc.md`. Use it as the model when another customer needs a similar pipeline.
