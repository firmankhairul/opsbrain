# Monthly Report: Markdown Structure

Scope: the section-by-section skeleton of the monthly report markdown (`report_template: default`). Status markers per section are defined in [monthly-wafr-and-writing.md](monthly-wafr-and-writing.md).

Each section maps 1:1 to a PPT slide. Use this exact heading structure — PPT conversion reads these headings verbatim.

Sections marked `(if any)` are omitted entirely when there is no data to report.

> **Keeping a customer's format identical every month.** The `.md` is the content
> source; `generate_ppt.py` owns a fixed layout (tables never split, title stays
> with its table, heading+items kept in one block, no emoji). To lock
> per-customer deck shaping so it never has to be redone — e.g. "Cost Summary =
> tables only", "Service Portfolio in one text box", or dropping a recurring note
> — record it in `monthly-report/custom/<slug>/deck-prefs.yaml` and keep the `.md`
> aligned to it. See [monthly-ppt-conversion.md](monthly-ppt-conversion.md).

---

```markdown
# Monthly Report — {Customer} | {Month Year}

**Period:** YYYY-MM-DD – YYYY-MM-DD  
**Account(s):** {profile list}  
**Generated:** YYYY-MM-DD  

---

## Executive Summary

{One narrative paragraph covering: total spend, MoM delta, key cost drivers,
utilization highlights, security posture, top risks. Business-readable — no bullets.}

### Approval Status

- Approved: {N} items (~USD {X}/mo savings)
- Pending: {N} items

### Top Recommendations

1. {Highest priority item}
2. {Second item}
3. {Third item}

---

## Service Portfolio

**Compute**
- Amazon EC2

**Database**
- Amazon RDS

**Networking & Content Delivery**
- Amazon VPC, Elastic Load Balancing

**Security, Identity & Compliance**
- AWS Security Hub, Amazon GuardDuty, AWS WAF

**Storage**
- Amazon S3, Amazon EBS

**Management & Governance**
- Amazon CloudWatch, AWS CloudTrail, AWS Compute Optimizer

{Add/remove domains based on what actually exists in the account. No tables.}

---

## Cost Summary

**Total:** USD {X} | **vs Last Month:** {↑/↓ USD Y (+Z%)} | **Daily Avg:** USD {A} | **Peak Day:** USD {B} ({date})

### Top 10 Services by Cost

| # | Service              | This Month (USD) | Prev Month (USD) | Delta      | % Change |
|---|----------------------|-----------------|-----------------|------------|----------|
| 1 | Amazon EC2           |                 |                 | ↑/↓        |          |
| 2 | ...                  |                 |                 |            |          |

### EC2 Instance Breakdown

| Instance Name | Type | Cost (USD) |
|---------------|------|-----------|
|               |      |           |

### EC2 Other (EBS, Snapshots, Data Transfer)

| Category          | Cost (USD) |
|-------------------|-----------|
| EBS Volumes       |           |
| EBS Snapshots     |           |
| Data Transfer     |           |

---

## Usage & Utilization

{Only include subsections for services that exist in the account.}

### Compute — EC2

| Instance | Type | CPU Avg | CPU Max | Finding          | Recommendation   |
|----------|------|---------|---------|------------------|------------------|
|          |      |         |         |                  |                  |

Compute Optimizer status: {enrolled / not enrolled}. Rightsizing savings estimate: USD {X}/mo.

### Database — RDS

| Instance ID | Class | Engine | CPU Avg | CPU Max | Conn Avg | Storage Used/Alloc | Finding |
|-------------|-------|--------|---------|---------|----------|--------------------|---------|
|             |       |        |         |         |          |                    |         |

### Cache — ElastiCache

| Cluster ID | Node Type | CPU Avg | Memory % | Evictions | Finding |
|------------|-----------|---------|----------|-----------|---------|
|            |           |         |          |           |         |

### Load Balancer

| Name | Type | Active Conn | Requests | 5xx Count | Finding |
|------|------|-------------|----------|-----------|---------|
|      |      |             |          |           |         |

### Storage

**EBS:** {total volumes} volumes, {N} unattached, {N} snapshots  
**S3:** {N} buckets, lifecycle policy coverage: {X}%  
**EFS:** {if present}

### Container — EKS/ECS

| Cluster | Type | Nodes | Status |
|---------|------|-------|--------|
|         |      |       |        |

---

## Security & Operational Posture

{Narrative. Cover: Security Hub findings, GuardDuty status, CloudTrail, WAF, KMS,
IAM anomalies, backup coverage. End with visibility limitations if any access was denied.}

---

## WAFR Observations

| Pillar                  | Status | Observation                        | Priority |
|-------------------------|--------|------------------------------------|----------|
| Operational Excellence  | GOOD   |                                    |          |
| Security                | FAIR   |                                    | MED      |
| Reliability             | GOOD   |                                    |          |
| Performance Efficiency  | FAIR   |                                    | MED      |
| Cost Optimization       | NEEDS WORK |                                    | HIGH     |
| Sustainability          | GOOD   |                                    |          |

*Based on monthly operational telemetry. Not a formal AWS Well-Architected Review.*

---

## Recommendations

| # | Recommendation                        | Priority | Est. Impact             | Approval |
|---|---------------------------------------|----------|-------------------------|---------|
| 1 |                                       | HIGH     | Save ~USD X/mo          | Pending |
| 2 |                                       | HIGH     | {risk statement}        | Pending |
| 3 |                                       | MED      | Save ~USD X/mo          | Pending |

{Sort HIGH first. Every row must have Est. Impact — either USD savings or a risk statement.}

---

## Cost Optimization Opportunities (if any)

{Include only when there are identifiable savings not already captured in Recommendations.
Use this section for quick wins: idle resources, unattached volumes, old snapshots, oversized instances.}

| Resource         | Current State      | Recommended Action     | Est. Savings (USD/mo) |
|------------------|--------------------|------------------------|-----------------------|
| {EBS vol-xxx}    | Unattached 30d     | Delete or snapshot     | {X}                   |
| {EC2 i-xxx}      | CPU <5% avg        | Downsize to t3.small   | {X}                   |

---

## Tickets This Period (if any)

{List all tickets from {customer}/tickets/ within the report period.
Include ticket ID, title, status, and resolution summary.}

| Ticket ID                          | Title               | Status   | Resolution Summary     |
|------------------------------------|---------------------|----------|------------------------|
| TKT-YYYY-MM-DD-{slug}              |                     | Resolved |                        |

---

## Pending Validation

{Narrative. Items not validated this period — e.g., missing access, deferred checks, open questions.
One paragraph per item. No tables.}
```

