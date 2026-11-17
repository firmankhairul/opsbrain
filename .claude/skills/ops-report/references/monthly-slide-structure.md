# Monthly Report: Slide Structure and Design Spec

Scope: the section order to write, presentation rules, and visual design spec for `report_template: default` decks. `generate_ppt.py` renders the draft's own section order, so this is the structure the markdown should follow. Conversion mechanics live in [monthly-ppt-conversion.md](monthly-ppt-conversion.md).

## Default Output Structure (STRICT ORDER — default reports only)

Generate default PPT-friendly reports with these slides. Use the Example MSP Compute PPT template as base. This section applies to `monthly_report.report_template: default` only.

For `monthly_report.report_template: custom`, keep the custom source's sections and content. Clean the presentation visually so it matches the Example MSP template, but do not add, remove, merge, or rename content sections unless the user explicitly asks.

### SLIDE 1: Cover
Customer name, period, "Example MSP COMPUTE 2026", "Monthly Report".

### SLIDE 2: Who Are We (Example MSP intro — keep unchanged)

### SLIDE 3: Executive Summary
Uses **3-box layout** (see Presentation Design Spec → Executive Summary Slide Layout):

- **Top box (narrative)**: Full paragraph summarising ALL findings. No bullet points, no tables.
  Cover: total spend, MoM change, daily trend, cost drivers, utilization highlights,
  security posture, key risks. Business-readable.
- **Bottom-left box (Approval Status)**: Count of approved vs pending recommendations + total estimated savings from approved items.
- **Bottom-right box (Top Recommendations)**: Top 3-5 recommendations in short bullet form, HIGH priority first.

**"So what" rule**: Every data point must be followed by a business insight.
Do not just state numbers — explain what they mean for the customer.
Example: "Spend increased 12% MoM (USD 1,200) driven by new EKS workload
deployment in week 2. Network cost remains 34% of total — NAT Gateway is the
dominant driver and represents the highest optimization opportunity this period."

Font: Instrument Sans (Regular, Medium, Semibold max).

### SLIDE 4: Service Portfolio by Domain
Simple domain list, no tables. Format:

```
Compute
  Amazon EC2

Security, Identity & Compliance
  AWS Security Hub, Amazon GuardDuty, AWS WAF, AWS KMS, AWS Secrets Manager

Networking & Content Delivery
  Amazon VPC, Elastic Load Balancing

Storage
  Amazon S3, Amazon EBS

Management & Governance
  Amazon CloudWatch, AWS CloudTrail, AWS Compute Optimizer, AWS Cost Explorer

Application Integration
  Amazon SNS, Amazon SQS

Commercial
  Tax, AWS CloudShell
```

### SLIDE 5: Cost Summary
Use tables for cost data. Include:
- Top 10 service cost drivers table — **must include MoM delta column** (↑/↓ USD and % vs previous month per service)
- EC2 BoxUsage per-instance cost table
- EC2 Other breakdown (EBS volume, snapshot, data transfer)
- Budget status if configured
- Total + MoM + avg daily + peak/lowest as summary line
Tables: dark red header row (#BC1823), white text, Instrument Sans font.

Top 10 table format:

| # | Service | This Month (USD) | Prev Month (USD) | Delta | % Change |
|---|---------|-----------------|-----------------|-------|----------|
| 1 | Amazon EC2 | 5,405.55 | 5,240.10 | ↑165.45 | +3.2% |

### SLIDE 6: Usage & Utilization Summary
Report utilization for **all services in use**, not just EC2. Sections by service:

**Compute (EC2)**:
Table: Instance name, type, CPU avg/max, finding, recommendation.
Include Compute Optimizer status and rightsizing savings estimate.

**Database (RDS/Aurora)**:
Table: Instance ID, class, engine, CPU avg/max, connections avg/max, storage used/allocated, finding.
Flag: over-provisioned (CPU <10%, connections <20% of max), storage nearly full (>80%).

**Cache (ElastiCache/Redis/Memcached)**:
Table: Cluster ID, node type, CPU avg, memory usage %, connections, evictions, finding.

**Load Balancer (ALB/NLB/CLB)**:
Table: LB name, type, active connections, request count, 5xx count, finding.
Flag: idle LBs (0 healthy targets or <10 requests/day).

**Storage (S3/EBS/EFS)**:
- EBS: total volumes, unattached volumes, snapshot count
- S3: bucket count, total size (if accessible), lifecycle policy coverage
- EFS: throughput mode, size

**Container (EKS/ECS)**:
- Cluster status, node count, pod count (if kubectl accessible)
- Nodegroup instance types and scaling config

**Network (NAT Gateway/VPC Endpoints)**:
- NAT GW: bytes processed, cost attribution
- VPC Endpoints: count, usage

**Serverless (Lambda/Fargate)** (if present):
- Invocation count, error rate, duration avg

Only include sections for services that **actually exist** in the customer's account.
Skip sections for services not in use.

### SLIDE 7: Security & Operational Posture
Narrative format. Cover: Security Hub, GuardDuty, CloudTrail, WAF, KMS, Inspector,
IAM, Backup, Budget. Include visibility limitations section at the end.

### SLIDE 8: WAFR-Informed Observations
Table with 6 pillars + observation + priority. Disclaimer line: "Based on monthly
operational telemetry. Not a formal AWS Well-Architected Review."

### SLIDE 9: Recommendations & Approval
Table: #, Recommendation, Priority, Est. Impact, Approval. Summary line with total savings.
Sort by priority (HIGH first).

**Est. Impact column** — every recommendation must include either:
- Estimated monthly savings (USD) if cost-related, OR
- Risk statement if security/reliability-related (e.g., "No drift detection — compliance blind spot")

Example:

| # | Recommendation | Priority | Est. Impact | Approval |
|---|---------------|----------|-------------|----------|
| 1 | Rightsize 4 underutilized instances | HIGH | Save ~USD 200/mo | Pending |
| 2 | Enable Config rules across accounts | HIGH | No drift detection — compliance gap | Pending |
| 3 | Review NAT Gateway routing | MED | Save ~USD 150/mo | Pending |

### SLIDE 10: Pending Validation / Follow-Up
Narrative per item. Items not validated this period. No tables.
Do NOT include Service Screener notes or Report Metadata in this section.

### SLIDE 11: Example MSP Clients (keep unchanged)

### SLIDE 12: Thank You (keep unchanged)

## Presentation Rules

- Canvas: 16:9 widescreen (960 × 540 px / 10 × 5.625 inches). Safe margins: 56 px (0.58").
- Font: Instrument Sans for all slides (Regular 400, Medium 500, Semibold 600 max — no bold/extrabold).
- Logos: Secondary Red Logo on Cover (top left); Primary Red Logo on content, dividers, diagrams, closing (top right).
- Slide numbering: Two-digit format (`01`, `02`) at bottom right of content slides only.
- Tables: dark red header (#BC1823), white header text, alternating body rows.
- Slide titles: white, Instrument Sans Medium (UPPERCASE).
- Body text: light gray (#CCCCCC) on dark background, white for emphasis.
- See [monthly-deck-rules.md](monthly-deck-rules.md) and `docs/standards/ics-brand-guidelines.md` for full design system details.
- Do not use ASCII box-drawing characters (│├└┌).
- Section slides without tables use narrative/paragraph text.
- Only Cost, Utilization, WAFR, and Recommendations slides use tables.
- Executive Summary and Security are prose, not tables.
- Service Portfolio is a simple domain list, not a table.
- Do not include Service Screener or Report Metadata in customer-facing output.

## Presentation Design Spec

### Layout Grid
- Title area: top 0.5", left 1.2" (avoid Example MSP logo at top-left)
- Content area: top 1.5", left 0.8", right margin 0.5", bottom 0.5"
- Max content width: 8.5"

### Executive Summary Slide Layout (3-box)

```
┌─────────────────────────────────────────────────┐
│  EXECUTIVE SUMMARY (title)                      │
├─────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────┐ │
│ │  Executive Summary (narrative box - top)    │ │
│ │  Full paragraph: spend, MoM, drivers,       │ │
│ │  utilization, security, key risks           │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌──────────────────────┐ ┌────────────────────┐ │
│ │  Approval Status     │ │  Top               │ │
│ │  (bottom-left box)   │ │  Recommendations   │ │
│ │                      │ │  (bottom-right box)│ │
│ │  • Approved: 2       │ │  • Rightsizing     │ │
│ │  • Pending: 3        │ │  • NAT optimize   │ │
│ │  • Total savings:    │ │  • Config rules    │ │
│ │    ~USD 350/mo       │ │                    │ │
│ └──────────────────────┘ └────────────────────┘ │
└─────────────────────────────────────────────────┘
```

- **Top box**: rounded rectangle, full width, contains executive narrative paragraph
- **Bottom-left box**: rounded rectangle, ~48% width, approval summary (approved/pending counts + total estimated savings)
- **Bottom-right box**: rounded rectangle, ~48% width, top 3-5 recommendations (short bullet form, HIGH priority first)
- Box style: subtle border (#444444), fill semi-transparent dark (#1A1A1A at 90% opacity), rounded corners 0.1"
- Gap between top and bottom boxes: 0.2"
- Gap between bottom-left and bottom-right: 0.15"

### Typography (Example MSP Brand Kit 2026)
- Slide title: Instrument Sans Medium, 24pt (UPPERCASE), white (#FFFFFF)
- Body text: Instrument Sans Regular, 11pt, light gray (#CCCCCC)
- Box title/label: Instrument Sans SemiBold, 12pt, white (#FFFFFF)
- Table header: Instrument Sans SemiBold, 10pt, white (#FFFFFF)
- Table body: Instrument Sans Regular, 9pt, dark (#333333) on light or light (#DDDDDD) on dark
- Caption/footnote: Instrument Sans Regular, 8pt, Cool Grey (#5A5852)

### Tables
- Header row: dark red background (#BC1823), white text
- Body rows: alternating row fills (`#2A2A2E` and `#35353A` on dark)
- Cell padding: 0.05" vertical, 0.1" horizontal
- Max rows per slide: 12 — if more, split to continuation slide with "(continued)" title
- Column alignment: text left, numbers right

### Colors
- Primary Brand Accent: #BC1823 (Dark Red)
- Critical Highlight / Focus: #EC1C24 (Bright Red)
- Muted / Caption: #5A5852 (Cool Grey)
- Base Dark: #000000 / #1A1A1A
- Neutral Light: #F3F0E9 (Paper) / #FFFFFF (White)

### Overflow Rules
- Cost top 10 table: always fits 1 slide
- EC2 utilization table: split at 12 rows, add "(continued)" title
- Recommendations: split at 8 rows
- If narrative exceeds slide space, reduce font to 10pt minimum before splitting

