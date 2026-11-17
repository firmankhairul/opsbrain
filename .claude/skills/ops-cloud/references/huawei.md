# Huawei Cloud playbooks

Scope: Huawei Cloud troubleshooting playbooks, risk examples, and golden signals via `hcloud` CLI. Pass `--cli-profile <name>` and `--region <region>` on every call (default region: `ap-southeast-4`).

## Risk examples

- **L1:** `list`, `show`, `ces alarms list`.
- **L2:** `ecs servers stop/start/reboot`, `vpc security-groups rules create`, flavor change, CCE node scale/upgrade, ELB health check tuning, NAT spec upgrade.
- **L3:** `ecs servers delete`, `rds instances delete`, `obs delete`.

Change Proposal fields: Profile, Region, Action, Target, Why, Risk, Rollback.

## ECS unreachable
1. `hcloud ecs servers show` (status, fault info).
2. Check security group rules and VPC routing.
3. Check Cloud Eye (CES) alarms for health status.

## High resource utilization
1. `hcloud ces metric-data list` (CPU, memory, disk I/O).
2. Check instance flavor vs workload. Correlate with LTS logs.
3. Propose flavor change (L2).

## RDS connectivity
1. `hcloud rds instances show` (status, private IP, port).
2. Verify the SG allows traffic from the application source.
3. Propose SG rule update (L2) or instance scale (L2).

## CCE cluster issues
1. `hcloud cce clusters show` (status, version).
2. `hcloud cce nodes list` + `kubectl get nodes`.
3. Propose node scale or upgrade (L2).

## ELB / load balancer
1. `hcloud elb loadbalancers show`: operating/provisioning status.
2. `hcloud elb pools show` + `hcloud elb members list`: unhealthy backends.
3. CES `m7_in_Bps`, `m8_out_Bps`, `unhealthy_members`.
4. Backend unhealthy: check ECS status and SG. Propose health check tuning (L2).

## OBS / object storage
1. `hcloud obs buckets get-policy`: explicit denies, public access.
2. `hcloud obs buckets get-lifecycle`: transition/expiration rules.
3. Cross-region replication config for DR compliance.

## LTS / Log Tank Service
1. `hcloud lts log-groups list` + `hcloud lts log-streams list`: verify collection is active.
2. Check LTS alarm rules for keyword triggers.
3. Verify log transfer tasks to OBS for retention.

## VPN
1. `hcloud vpn connections show`: `status` (ACTIVE / DOWN / ERROR).
2. Verify IKE/IPsec policy parameters match the on-prem peer.
3. Check VPN gateway routes and VPC route table propagation.

## DNS
1. `hcloud dns zones list`: zone status (ACTIVE / PENDING).
2. `hcloud dns recordsets list`: verify A / CNAME / MX records.
3. Private zones: verify VPC association.

## NAT gateway
1. `hcloud nat snat-rules list`: outbound access for ECS.
2. `hcloud nat dnat-rules list`: port mapping for inbound.
3. CES connection count and bandwidth utilization.
4. Connection limit reached: propose spec upgrade (L2).

## Security posture
1. **HSS:** `hcloud hss risk-item-statistics`: vulnerability scan, intrusion detection.
2. **SecMaster:** security incident triage, threat intelligence.
3. **CTS:** Cloud Trace Service query for suspicious operations.
4. **WAF:** OWASP Top 10, CC attack protection, custom rules.

## Golden signals

| Signal | CES namespace / metric | Threshold |
|---|---|---|
| CPU | SYS.ECS / `cpu_util` | < 85% |
| Memory | AGT.ECS / `mem_util` | < 85% |
| Latency | SYS.ELB / `m7_l7_resp_time` | p99 < X ms |
| Errors | SYS.ELB / `m4_l7_srv_err_count` | < X/min |

## Session
Expired: stop and return `hcloud configure sso --cli-profile <name>`.
