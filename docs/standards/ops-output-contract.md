# Ops Output Contract

All specialist skills (`ops-cloud`, `ops-platform`, `ops-troubleshoot`, `ops-security`, `ops-odoo`, `ops-report`) must emit a consistent response contract.

## Required Sections

1. `Current State` - factual observed state from live checks.
2. `Findings` - analysis and likely root causes.
3. `Risk/Impact` - blast radius and operational impact.
4. `Change Proposal` - explicit proposed actions.
5. `Rollback` - exact steps to revert.
6. `Verification` - post-action checks and expected signals.
7. `Docs Delta` - what documentation should be updated.

## Mutation Gate

- Any mutating action requires explicit approval after `Change Proposal`.
- If approval is missing, stop at analysis/proposal.

## Language Standard

- Operational output is written in English.
- Keep cloud and platform terms in their native technical names.
