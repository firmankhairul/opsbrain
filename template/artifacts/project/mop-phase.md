---
type: mop
summary: "{title}: MoP for one project phase"
tags: [project, mop]
applies_to: []
parent:
project: {slug}
---
# MoP: {title}

**Project:** projects/{slug}/ · **Phase:** <n> <name> · **Phase issue:** # · **Status:** proposed <!-- proposed | approved | executed | rolled-back -->
**Prepared:** {date} · **Executes:** <date, window start-end, timezone>

A project MoP is complete and step-by-step: it is executed by someone else, in another
window. Do not write "follow runbook X"; copy the steps in and add the parameters. Name
the runbook in `parent:` so the shared procedure stays traceable.

## Sign-off

| Role | Name | Date |
|------|------|------|
| Prepared (Example MSP) | | {date} |
| Reviewed (Example MSP) | | |
| Approved (customer) | | |

## Scope of this phase

- In this phase:
- Not in this phase:

## Prerequisites (go/no-go, checked before the window)

| # | Prerequisite | How verified | Verified by | Status |
|---|--------------|--------------|-------------|--------|
| 1 | Backup or snapshot taken and restorable | | | Pending |
| 2 | Access and credentials ready | | | Pending |
| 3 | Customer informed, window confirmed | | | Pending |
| 4 | Rollback tested or at least rehearsed | | | Pending |

## Communication plan

| When | Who | Channel | Message |
|------|-----|---------|---------|
| T-1 day | PIC customer | | window reminder |
| T-0 start | | | started |
| Each go/no-go | | | result |
| T-0 end | | | done or rolled back |

## Procedure

Every step: exact command or console action, expected result, who runs it, time budget.
A go/no-go row stops the procedure until someone decides.

| # | Step | Command / action | Expected result | PIC | Time |
|---|------|------------------|-----------------|-----|------|
| 1 | | | | | |
| 2 | **Go/no-go** | criteria: | continue or roll back | | |

## Verification

| # | Check | Command / action | Expected | Result |
|---|-------|------------------|----------|--------|
| 1 | | | | |

## Rollback

| Trigger | Step | Command / action | Time | Data loss |
|---------|------|------------------|------|-----------|
| | | | | |

## Execution record

| Step | Started | Finished | Result | Evidence (comment link) |
|------|---------|----------|--------|--------------------------|
| | | | | |

## Post-execution

- Docs Delta applied (`<slug>/docs/*`, `Terakhir diverifikasi`): 
- Phase issue resolved with `issue_resolve`: 
- Problems worth adding to the runbook table: 
