# Assessment: Well-Architected Framework Review (WAFR)

**ID:** ASMT-2026-11-10-wafr-review
**Customer:** Acme Retail
**Date:** 2026-11-10
**Author:** Kiro CLI with the AWS Well-Architected security MCP, reviewed by a cloud engineer
**Status:** final

## Verdict

Overall posture is GOOD with 5 findings: 1 high, 2 medium, 2 low. The high
finding (unencrypted uploads bucket) is fixed first.

## Scope

**In scope:** all six pillars, account 123456789012, read-only checks.

**Excluded:** workload questions that need the customer's product team.

## Current State

**Verified:** 2026-11-10 via read-only AWS calls and the Well-Architected security MCP.

| Pillar | Rating | Main gap |
|--------|--------|----------|
| Operational Excellence | FAIR | No runbooks for database failover |
| Security | NEEDS WORK | Uploads bucket not encrypted, Config off |
| Reliability | FAIR | Single NAT gateway, no restore test |
| Performance Efficiency | GOOD | None |
| Cost Optimization | GOOD | Idle bastion could be scheduled |
| Sustainability | GOOD | None |

## Findings

| ID | Pillar | Severity | Finding | Issue |
|----|--------|----------|---------|-------|
| F-01 | Security | High | Uploads bucket has no default encryption | #1 |
| F-02 | Security | Medium | Bucket policy does not require TLS | #1 |
| F-03 | Reliability | Medium | No tested database restore | #1 |
| F-04 | Reliability | Low | Single NAT gateway | #1 |
| F-05 | Security | Low | AWS Config not enabled | #1 |

## Recommendation

Fix F-01 and F-02 first through one MoP (change-low). Plan F-03 to F-05 into the
next maintenance window. Each finding is an action item in issue #1.
