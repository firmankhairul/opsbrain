# AWS playbooks

Scope: AWS troubleshooting playbooks, risk examples, golden signals, and multi-account notes. Pass `--profile <name>` and `--region <region>` on every call.

## Tooling

- AWS CLI with `--profile`/`--region`, or the `aws-core` plugin MCP (`aws___call_aws` / `aws___run_script`).
- Docs: `aws___search_documentation` (then `aws___read_documentation`). Cite documentation URLs in findings.

## Risk examples

- **L1:** `Describe*`, `List*`, `Get*`, `Search*`, CloudWatch metrics.
- **L2:** `ModifyInstanceType`, security group updates, `StopInstances`, `RebootInstances`, `modify-volume`, `modify-vpn-tunnel-options`, `put-inline-policy-to-permission-set`.
- **L3:** `TerminateInstances`, `DeleteDBCluster`, purging an S3 bucket, `DeleteVPC`, orphan-resource cleanup.

## EC2 / compute unreachable
1. `describe-instance-status` (system/instance checks).
2. `describe-instances` (state, VPC, subnet) + `describe-security-groups` (ingress) + `describe-route-tables` (IGW/NAT).
3. If SG/routing OK but status check failed: propose `reboot` (L2) or `stop/start` (L2).

## High resource utilization (CPU / memory / I/O)
1. `cloudwatch get-metric-statistics` (`CPUUtilization`, `DiskReadBytes`, last 1h).
2. Correlate with EKS pod limits or RDS slow queries.
3. Propose vertical scaling (L2) or application-level investigation.

## Disk full / EBS volume
1. CloudWatch `DiskSpaceUtilization` (if CloudWatch Agent) or EBS IOPS.
2. `describe-volumes`: check type (gp2/gp3) and size.
3. Clean up first, then propose `modify-volume` (L2).

## RDS connectivity / performance
1. `describe-db-instances` (status, endpoint, port).
2. Verify the SG allows traffic from the application source.
3. Check `DatabaseConnections` and `CPUUtilization`. If `max_connections` is hit: analyze connection leaks or propose scaling (L2).

## EKS / Kubernetes node issues
1. `describe-cluster` + `describe-nodegroup`.
2. `describe-instances` for ASG nodes. Check `NotReady` (delegate pod analysis to `ops-platform`).
3. Verify node SG allows 10250 (kubelet) and 443 (API server).

## Cost and optimization
1. `ce get-cost-and-usage` (group by `SERVICE`, last 7 days).
2. Identify orphaned resources (EIPs, detached EBS, idle LBs).
3. Propose cleanup (L3) or RI / Savings Plans. Full method in [finops.md](finops.md).

## VPN site-to-site
1. `describe-vpn-connections`: check `TunnelOptions` and `Status` (UP/DOWN).
2. Check `BgpStatus` and route propagation in `describe-route-tables`.
3. CloudWatch `TunnelState`, `TunnelDataIn`, `TunnelDataOut`.
4. If DOWN: check the on-prem peer config (IKE version, PSK, phase 2). Propose `modify-vpn-tunnel-options` (L2).

## ELB / ALB / NLB
1. `describe-target-health`: identify unhealthy targets and failure reasons.
2. CloudWatch `HTTPCode_ELB_5XX_Count` vs `HTTPCode_Target_5XX_Count` to separate LB from backend.
3. `describe-listeners` for the cert ARN, then `acm describe-certificate` for expiry.
4. Check access logging via `describe-load-balancer-attributes`.

## S3 bucket issues
1. Access denied: `get-bucket-policy` + `get-bucket-acl` + `get-public-access-block`.
2. `get-bucket-replication` for CRR status.
3. `get-bucket-lifecycle-configuration` for unexpected data loss.
4. `get-bucket-encryption` for SSE config.

## Organizations and SCPs
1. Unexpected permission denied: `organizations list-policies` + `describe-policy` for SCPs.
2. `list-accounts` + `list-organizational-units-for-parent` for the OU hierarchy.
3. Verify IAM role trust policies for cross-account `sts:AssumeRole`.

## CloudWatch alarms
1. `describe-alarms`: check `StateValue` (OK / ALARM / INSUFFICIENT_DATA) and `StateReason`.
2. `sns list-subscriptions-by-topic` for notification targets.
3. Review `TreatMissingData`; a common cause of false alarms.

## Route 53 / DNS
1. `get-health-check-status` for endpoint health.
2. `test-dns-answer` for record resolution.
3. Failover routing: verify primary/secondary health check associations.

## CloudFront / CDN
1. CloudWatch `CacheHitRate`: a low ratio means origin overload; check cache policies.
2. `4xxErrorRate` / `5xxErrorRate`. `get-distribution` for origin config.
3. `WebACLId` for associated WAF rules.

## Lambda
1. CloudWatch `Throttles`, then `get-function-concurrency` for reserved limits.
2. `Duration` spikes mean cold starts; check provisioned concurrency.
3. `Errors` + CloudWatch Logs for stack traces. Check runtime, memory, timeout.
4. `get-function-event-invoke-config` for DLQ / OnFailure destination.

## IAM and Identity Center (SSO)
1. `sso-admin list-permission-sets`, then `describe-permission-set` to find the target.
2. `get-inline-policy-for-permission-set` + `list-managed-policies-in-permission-set` for the current policy.
3. Edit the inline policy JSON, then `put-inline-policy-to-permission-set` (L2).
4. `provision-permission-set --target-type ALL_PROVISIONED_ACCOUNTS` to apply.

## Security posture
1. **GuardDuty:** `list-findings` filtered by severity. Triage CRITICAL/HIGH first.
2. **Security Hub:** `get-findings` with `SeverityLabel=CRITICAL`. Check CIS/FSBP compliance.
3. **Config:** `describe-compliance-by-config-rule` for drift detection.
4. **CloudTrail:** `lookup-events` for suspicious API calls.

## Golden signals

| Signal | Namespace / metric | Threshold |
|---|---|---|
| Latency | AWS/ApplicationELB `TargetResponseTime` | p99 < X ms |
| Errors | AWS/ApplicationELB `HTTPCode_Target_5XX` | < X% |
| Saturation | AWS/EC2 `CPUUtilization` | < 85% |
| Availability | AWS/Route53 `HealthCheckStatus` | = 1 |

## Multi-account and Organizations
- Always pass `--profile` and `--region`.
- Cross-reference Transit Gateway / VPC peering for inter-account connectivity.
- Check SCPs when permissions are unexpectedly denied.

## Session
`ExpiredToken` or `SSOTokenLoadError`: stop and return `aws sso login --profile <name>`.
