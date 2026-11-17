# Monthly Report: WAFR Mapping, Writing Rules, Status Markers

Scope: mapping collected data to Well-Architected pillars, narrative writing rules, and the per-section status markers used while drafting.

## WAFR Pillar Mapping Guide

Map findings from collected data to pillars:

| Data Source | Maps to Pillar |
|-------------|---------------|
| CloudTrail, CloudWatch alarms, backup config | Operational Excellence |
| Security Hub, GuardDuty, CloudTrail validation, IAM | Security |
| Multi-AZ, backup retention, ASG, health checks | Reliability |
| Compute Optimizer, instance sizing, utilization | Performance Efficiency |
| Cost trends, idle resources, RI/SP, rightsizing | Cost Optimization |
| Instance generation, Graviton, stopped instances | Sustainability |

**Rule**: Only elaborate on pillars rated FAIR or NEEDS WORK. GOOD pillars get a one-line summary only.

## Writing Rules

1. Language: **English**
2. Concise, decision-oriented narrative
3. Explicit figures (USD, percentages, counts)
4. Exception-based reporting (highlight problems, not "everything is fine")
5. If access denied → state visibility limitation, continue
6. **Exclude AWS Config discussion**
7. Recommendations must be **account-based** with pillar tag
8. Tables for structured data

## Section Status Markers

Every section in the `.md` file starts with a status blockquote. Update it each time you write a section — do not leave stale markers.

| Marker | Meaning |
|--------|---------|
| `> TODO` | Not started — skeleton only |
| `> In Progress` | Collecting data / writing |
| `> Done` | Section complete |
| `> Limited — {reason}` | Access denied or data unavailable |

**Rule:** Write the section content first, then update the marker in the same file edit. After each section, tell the user which section just completed and what's next.

Example progress update after Cost Summary:
> Cost Summary done — total USD 4,231 (+8% MoM). Next: Usage & Utilization.

