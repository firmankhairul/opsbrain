# Alibaba Cloud playbooks

Scope: Alibaba Cloud troubleshooting playbooks, credential checks, risk examples, and golden signals via `aliyun` CLI. Pass `--profile <name>` and confirm `RegionId` before every call (default varies per customer; check `docs/overview.md`).

## Risk examples

- **L1:** `Describe*`, `List*`, `GetCallerIdentity`.
- **L2:** `ecs StopInstance/StartInstance/RebootInstance`, `alidns AddDomainRecord/UpdateDomainRecord`, `vpc AuthorizeSecurityGroup`, instance type change, RDS whitelist update, ACK node pool scale/upgrade.
- **L3:** `ecs DeleteInstance`, `rds DeleteDBInstance`, `oss DeleteBucket`, `alidns DeleteDomainRecord`.

Change Proposal fields: Profile, Region, Action, Target, Why, Risk, Rollback. Correlate with `docs/instances.md` and `docs/network.md`.

## Credential check
- Verify identity before acting: `aliyun --profile <name> sts GetCallerIdentity`.
- Check effective permissions: `aliyun --profile <name> ram ListPoliciesForUser --UserName <ram-user>` (or `ListPoliciesForRole` for RAM roles). A successful read does not imply write access.
- Credentials are static AK/SK per profile; there is no SSO browser login. If missing or invalid, stop and ask the user to run `aliyun configure --profile <name>` (prompts for Access Key Id, Access Key Secret, Default Region Id). Verify with `aliyun --profile <name> configure list` (`Valid` / `Invalid`) before proceeding.

## ECS unreachable
1. `aliyun ecs DescribeInstances --InstanceIds '["i-xxx"]'`: check `Status`, `OperationLocks`.
2. `aliyun ecs DescribeSecurityGroupAttribute`: verify inbound rules.
3. `aliyun vpc DescribeRouteTableList`: verify VPC routing.
4. Check CloudMonitor (`cms`) alarms for host health.

## High resource utilization
1. `aliyun cms DescribeMetricList --Namespace acs_ecs_dashboard --MetricName CPUUtilization` (also `memory_usedutilization`, disk I/O metrics).
2. Compare instance type/spec vs workload. Correlate with SLS (Log Service) logs if enabled.
3. Propose instance type change (L2, requires stop/start).

## RDS connectivity
1. `aliyun rds DescribeDBInstanceAttribute`: `DBInstanceStatus`, `ConnectionString`, `Port`.
2. `aliyun rds DescribeDBInstanceNetInfo`: whitelist / VPC connection.
3. `aliyun rds DescribeDBInstanceIPArrayList`: verify the source IP is whitelisted.
4. Propose whitelist update (L2) or instance class upgrade (L2).

## ACK (Container Service for Kubernetes)
1. `aliyun cs DescribeClusterDetail`: cluster `state`, version.
2. `aliyun cs DescribeClusterNodes` + `kubectl get nodes`.
3. Propose node pool scale or version upgrade (L2).

## SLB / ALB
1. `aliyun slb DescribeLoadBalancerAttribute`: status, listeners.
2. `aliyun slb DescribeHealthStatus`: unhealthy backend servers.
3. CloudMonitor `acs_slb_dashboard`: `Qps`, `Traffic`, backend health metrics.
4. Backend unhealthy: check ECS status and security group. Propose health-check tuning (L2).

## OSS / object storage
1. `aliyun oss api GetBucketPolicy`: explicit denies, public-read/write exposure.
2. `aliyun oss api GetBucketLifecycle`: transition/expiration rules.
3. `aliyun oss api GetBucketReplication`: cross-region replication for DR compliance.
4. Flag public-read/write buckets as security findings before any other action.

## AliDNS
1. `aliyun alidns DescribeDomains`: confirm the domain is hosted on Alibaba Cloud DNS (`NS7/NS8.ALIDNS.COM`) before assuming write access here.
2. `aliyun alidns DescribeDomainRecords --DomainName <domain>`: current A / CNAME / MX / TXT records.
3. `AddDomainRecord` / `UpdateDomainRecord` is L2: show current state + proposed record before executing.
4. CA domain-control-validation (DCV) CNAME: confirm exact Host/Value from the CA before adding; confirm propagation with `dig CNAME <host> +short` after the change.

## Security posture
1. **RAM:** `aliyun ram ListPoliciesForUser` / `ListUsers`. Flag `AdministratorAccess` on non-break-glass accounts as a finding.
2. **Security Center:** `aliyun sas DescribeSuspiciousEvents`: vulnerability scan, intrusion detection.
3. **ActionTrail:** `aliyun actiontrail LookupEvents`: suspicious/unauthorized API calls.
4. **WAF:** `aliyun waf-openapi DescribeDomain`: OWASP Top 10 rules, CC attack protection status.

## Golden signals (CloudMonitor / cms)

| Signal | CMS namespace / metric | Threshold |
|---|---|---|
| CPU | acs_ecs_dashboard / `CPUUtilization` | < 85% |
| Memory | acs_ecs_dashboard / `memory_usedutilization` | < 85% |
| Latency | acs_slb_dashboard / `Rt` | p99 < X ms |
| Errors | acs_slb_dashboard / `UnhealthyServerCount` | 0 |
