---
name: ops-security
description: >-
  Run infrastructure security operations: firewall policy and VPN on Fortinet,
  endpoint detection and containment on CrowdStrike, WAF tuning, TLS
  certificate hygiene, vulnerability triage, and security incident response.
  Use when the task mentions Fortinet, FortiGate, FortiOS, firewall policy or
  rule, IPsec or SSL VPN tunnel, FortiGate HA, IPS, CrowdStrike, Falcon, EDR,
  detection, host containment or isolation, RTR, IOC, WAF, OWASP CRS, false
  positive block, rate limiting, SSL/TLS certificate expiry, weak cipher, HSTS,
  CVE, vulnerability, KEV, patch SLA, trivy, checkov, tfsec, image or IaC
  scanning, GuardDuty finding triage, compromise, malware, or evidence
  preservation.
metadata:
  version: "4.0.0"
---

# Infrastructure Security Operations

Monitor, triage, and enforce security controls across firewalls, endpoints, web edges, and workloads.

## Engagement rules

- Enter through `ms-ops`: it resolves the customer, the profile, and reads `<slug>/docs/`. If this skill is invoked directly, call `get_customer` and read the customer docs before touching the account.
- Risk levels: **L1** read-only (Describe/List/Get, metrics, logs) runs without asking. **L2** scoped or reversible change needs a Change Proposal and explicit approval. **L3** destructive or wide blast radius needs an explicit warning, a Change Proposal, a Rollback Plan, and approval.
- Never guess a profile, account, subscription, or project. If ambiguous, ask one targeted question.
- Expired session: stop and return the exact login command; do not retry.
- Output contract: `Current State`, `Findings`, `Risk/Impact`, `Change Proposal`, `Rollback`, `Verification`, `Docs Delta` (drop proposal/rollback when read-only).

## Pick the reference

Read only the file you need.

| Topic | Read | When |
|---|---|---|
| Fortinet | [fortinet.md](references/fortinet.md) | FortiGate policy match, sessions, traffic logs, IPsec/SSL VPN, HA, firmware, IPS |
| CrowdStrike | [crowdstrike.md](references/crowdstrike.md) | Falcon host lookup, detections, RTR, containment, IOCs |
| Web and certs | [web-and-certs.md](references/web-and-certs.md) | WAF rules and false positives, rate limits, TLS cert expiry, ciphers, HSTS |
| Vulnerability | [vulnerability.md](references/vulnerability.md) | CVE severity/SLA, image and IaC scanning, common misconfig findings |
| Incident response | [incident-response.md](references/incident-response.md) | Active compromise, GuardDuty finding triage, evidence, recovery |

## Common method

1. **Observe (L1):** Audit policies, hit counters, logs; threat hunt.
2. **Triage:** Separate false positives from active threats before acting.
3. **Propose (L2/L3):** Change Proposal states Domain, Action, Blast Radius, Rollback.
4. **Act:** Only after approval. Back up the config before every change.
5. **Verify:** Test the intended traffic flow; watch for secondary alerts.

Domain safety rules:

- Risk mapping: L1 = policy review, hit counters, log analysis, threat hunting. L2 = add/modify a firewall rule, VPN config adjustment, scoped WAF exception, lift containment. L3 = host isolation/containment, deleting policies, global security config.
- Host isolation requires **double confirmation**: ask, restate impact (host loses network), ask again.
- Preserve evidence before remediation; never wipe or rebuild a suspect host first.
