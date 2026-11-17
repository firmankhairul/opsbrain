# FinOps playbooks

Scope: cloud cost analysis and optimization across AWS, Azure, GCP, and Huawei Cloud: spend breakdown, tag allocation, commitments (RI/SP/CUD), rightsizing, waste.

## Risk examples

- **L1:** cost queries, budget checks, recommendation reads.
- **L2:** budget creation, tag policy updates, rightsizing proposals.
- **L3:** RI / Savings Plan purchases, resource termination for cost savings.

## Method
1. **Inform:** pull cost data, identify top drivers, check tag coverage.
2. **Optimize:** identify quick wins, commitment opportunities, waste.
3. **Automate:** budget alerts, tag enforcement, scheduled shutdowns.
4. **Report:** present findings with estimated savings.

## Cost analysis workflow

### 1. Service-level breakdown
- Group by service, account/project, region.
- Top 10 services by cost, % of total, MoM change.

### 2. Tag-based allocation
- Cost per team / project / environment.
- Untagged resource %: always report, even if 0%.
- Tagging coverage rate per tag key.

### 3. Commitment coverage (RI/SP)
- Coverage rate: % of eligible usage covered.
- Utilization rate: % of purchased RI/SP actually used.
- On-Demand waste: spend that could be covered.
- Target: coverage 70-80%, utilization > 90%.

### 4. Trend analysis
- Monthly trend with MoM % change.
- Spikes > 20% from the rolling average.
- Anomalies > 2 standard deviations from the mean.

## Platform commands

AWS (or `aws-core:aws-billing-and-cost-management` for depth):
```
aws ce get-cost-and-usage --time-period Start=YYYY-MM-01,End=YYYY-MM-DD --granularity MONTHLY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE
aws ce get-rightsizing-recommendation --service AmazonEC2
aws compute-optimizer get-ec2-instance-recommendations
```

Azure:
```
az consumption usage list --start-date YYYY-MM-01 --end-date YYYY-MM-DD
az advisor recommendation list --category Cost
```

GCP:
```
gcloud billing accounts list
gcloud recommender recommendations list --recommender=google.compute.instance.MachineTypeRecommender
```

## Commitment guide

| Platform | Type | Best for | Discount |
|---|---|---|---|
| AWS | Compute Savings Plan | EC2 + Fargate + Lambda | Up to 66% |
| AWS | Standard RI | Stable EC2/RDS | Up to 72% |
| Azure | Reserved VM | Stable VMs | Up to 72% |
| Azure | Savings Plan | Dynamic compute | Up to 65% |
| GCP | CUD (resource) | vCPU + RAM | Up to 55% (3yr) |
| GCP | Spot VMs | Batch / CI | 60-91% |
| Huawei | RI | ECS/RDS | Up to 50% (3yr) |

## Optimization categories

| Category | Examples | Effort |
|---|---|---|
| Waste | Orphaned EIPs, detached EBS, idle LBs, stopped instances | Low |
| Rightsizing | Oversized EC2/VM, over-provisioned RDS | Low-Medium |
| Commitment | RI/SP purchases for stable workloads | Medium |
| Architecture | Graviton migration, serverless, spot instances | High |
| Scheduling | Dev/staging shutdown nights/weekends | Low |

## Cost report sections
1. **Executive summary:** total spend, potential savings, top 3 actions.
2. **Cost breakdown:** by service, team, environment.
3. **Optimization recommendations:** prioritized P1/P2/P3 with estimated savings.
4. **Savings summary table:** Current vs Optimized vs Monthly Savings.
