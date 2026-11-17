---
type: project
summary: "{title}: phases, dates, mandays"
tags: [project, timeline]
applies_to: []
---
# Timeline: {title}

Customer: {customer} · Prepared: {date} · Version: 1

Mandays are the estimate for quotation and capacity. They are not the issue weight
(`Bobot kerja`), which is set per phase issue with `issue_classify`.

| Phase | Deliverable | Start | End | Mandays | PIC | Depends on | Issue |
|-------|-------------|-------|-----|---------|-----|------------|-------|
| 0 Discovery | Current-state inventory, risks, go/no-go to design | | | | | | # |
| 1 Design | TDD approved by customer | | | | | 0 | # |
| 2 Preparation | Access, backups, tooling, communication plan, MoPs written | | | | | 1 | # |
| 3 Execution | Change executed per MoP (one row per wave if several) | | | | | 2 | # |
| 4 Verification and hypercare | Acceptance tests passed, monitoring stable for N days | | | | | 3 | # |
| 5 Handover | BAST signed, docs updated, BAU team briefed | | | | | 4 | # |
| | **Total** | | | **0** | | | |

## Milestones

| Milestone | Date | Evidence |
|-----------|------|----------|
| TDD approved | | |
| Execution window agreed | | |
| Acceptance signed | | |

## Assumptions

- 

## Change log

| Date | Change | Reason |
|------|--------|--------|
| {date} | Version 1 | initial plan |
