# Security Incident Response

Containment, evidence, communication, and recovery for a suspected compromise, plus first-pass GuardDuty finding triage.

## Response steps

1. **Containment:** isolate affected systems (EDR containment per [crowdstrike.md](crowdstrike.md), or a restrictive security group). Log every action with a timestamp.
2. **Evidence:** preserve logs, memory dumps, and disk images (EBS snapshots) before remediation. Keep chain of custody.
3. **Communication:** notify stakeholders per severity. Use the incident report template from `ops-report`.
4. **Recovery:** restore from known-good backups; verify integrity before returning to production.

## GuardDuty finding triage (AWS CLI, read-only)

1. `aws guardduty list-detectors --profile <p> --region <r>`.
2. `aws guardduty list-findings --detector-id <id> --finding-criteria '{"Criterion":{"severity":{"Gte":7}}}'` then `get-findings --finding-ids ...`.
3. Read `Type`, `Resource` (instance/access key), `Service.Action` (remote IP, API), `Count`, first/last seen.
4. Classify: expected behavior (scanner, known admin IP) -> document and propose a suppression rule (L2); otherwise treat as active and follow the response steps above.
