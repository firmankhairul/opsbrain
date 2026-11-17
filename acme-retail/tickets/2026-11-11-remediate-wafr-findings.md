# Remediate WAFR findings (Acme Retail)

**Type:** change-low
**Weight:** 3
**Status:** In progress

## Environment

- Customer: Acme Retail, account 123456789012, ap-southeast-1
- Source: ASMT-2026-11-10-wafr-review

## Masalah

The WAFR found five gaps. The high and medium security findings affect customer
uploads and must be fixed first.

## Action items

| No | Action | PIC | Status | Evidence |
|----|--------|-----|--------|----------|
| 1 | Enable default encryption on uploads bucket (F-01) | Cloud engineer | Done | MoP-2026-11-14-enable-s3-default-encryption |
| 2 | Add TLS-only bucket policy (F-02) | Cloud engineer | Done | Same MoP, step 4 |
| 3 | Run and document a database restore test (F-03) | Cloud engineer | Pending | - |
| 4 | Add a second NAT gateway (F-04) | Cloud engineer | Pending | Needs customer cost approval |
| 5 | Enable AWS Config with core rules (F-05) | Cloud engineer | Pending | - |

## Catatan & keputusan

- 2026-11-14: Customer approved the MoP for items 1 and 2.
- Kiro executed the approved steps and verified with `get-bucket-encryption`.
