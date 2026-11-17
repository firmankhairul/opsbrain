---
name: ops-troubleshoot
description: >-
  Host, network-path and database-engine troubleshooting on VMs and servers:
  Linux CPU/memory/disk/systemd via the USE method, connectivity via a layered
  ladder, and MySQL/MariaDB/PostgreSQL/Redis engine diagnostics. Use when a
  host shows high CPU or load, OOM killer, swap, disk full or inode
  exhaustion, I/O wait, a systemd service down or crash-looping, journald
  errors; when DNS is not resolving, a TLS/cert error or expiry, a port is
  unreachable (refused/timeout), firewall drops, routing, latency, packet
  loss or MTU issues; or when a database has slow queries, deadlocks or lock
  waits, replication lag, connection exhaustion, buffer pool/memory pressure,
  bloat/autovacuum, or Redis evictions and latency.
metadata:
  version: "4.0.0"
  replaces: "ops-linux ops-network ops-database"
---

# Host, Network & Database Troubleshooting

Localise a fault to one host resource, one network layer, or one database engine, then fix it with evidence.

## Engagement rules

- Enter through `ms-ops`: it resolves the customer, the profile, and reads `<slug>/docs/`. If this skill is invoked directly, call `get_customer` and read the customer docs before touching the account.
- Risk levels: **L1** read-only (Describe/List/Get, metrics, logs) runs without asking. **L2** scoped or reversible change needs a Change Proposal and explicit approval. **L3** destructive or wide blast radius needs an explicit warning, a Change Proposal, a Rollback Plan, and approval.
- Never guess a profile, account, subscription, or project. If ambiguous, ask one targeted question.
- Expired session: stop and return the exact login command; do not retry.
- Output contract: `Current State`, `Findings`, `Risk/Impact`, `Change Proposal`, `Rollback`, `Verification`, `Docs Delta` (drop proposal/rollback when read-only).

## Pick the reference

Read only the file the symptom needs. Open a second one only when the evidence crosses layers (e.g. OOM caused by a database, timeout caused by a full disk).

| Symptom / layer | Read | When |
|---|---|---|
| Host resource | [linux.md](references/linux.md) | High CPU/load, OOM, swap, disk full, inodes, I/O wait, systemd/journald, D-state processes |
| Network path | [network.md](references/network.md) | DNS, refused/timeout, firewall, routing, latency/loss, MTU, TLS/cert, tcpdump |
| Database engine | [database.md](references/database.md) | Slow query, lock/deadlock, replication lag, connections, buffer pool, bloat, Redis memory/latency |

Boundaries:

- Same symptom on a Kubernetes node, pod, or container runtime → `ops-platform`.
- Managed RDS / Aurora / Cloud SQL / ElastiCache → `ops-cloud` first (instance, parameter group, metrics, failover); use this skill only for query and lock tuning inside the engine.
- Firewall appliance (Fortinet) → `ops-security`.
- Cloud primitives (VPC, subnets, SG/NSG rules, Route53, ALB/NLB, TGW, EBS burst credits) → `ops-cloud`.

## Common method

**Reach the host.** Use the method in `<slug>/docs/access.md`: SSM Session Manager (`aws ssm start-session --target <instance-id> --profile <profile>`) where available, otherwise SSH through the documented bastion/jumphost. Never invent keys or hosts.

**Read-only first.** Run the L1 triage in the chosen reference before proposing anything. Record what the tools show and what they do not show.

**USE method (host).** For each resource (CPU, memory, disk capacity, disk I/O, network) check Utilization, Saturation, Errors. Localise to one resource before acting.

**Layer ladder (network).** Walk link → IP/route → reachability → DNS → L4 port → firewall → L7/TLS → wire capture. Test with a raw IP to rule DNS in or out. `tcpdump` last.

**Engine instrumentation (database).** Processlist / `pg_stat_activity`, slow log or statement digests, engine status. One category at a time: slow query, lock, replication, memory, connections.

**Capture evidence before any restart or kill.** A restart destroys the state that explains the fault. Save first:

```bash
ts=$(date +%Y%m%d-%H%M%S); d=/tmp/evidence-$ts; mkdir -p $d
uptime > $d/uptime; free -h > $d/free; df -h > $d/df; df -i > $d/df-i
ps aux --sort=-%mem | head -30 > $d/ps-mem; ps aux --sort=-%cpu | head -30 > $d/ps-cpu
dmesg -T | tail -200 > $d/dmesg; journalctl -p err -b --no-pager | tail -200 > $d/journal-err
systemctl show <svc> > $d/svc-show; journalctl -u <svc> -n 300 --no-pager > $d/svc-log
ss -tanp > $d/ss
```

For databases also save the processlist / `pg_stat_activity`, `SHOW ENGINE INNODB STATUS`, and current global variables. Snapshot configs (`cp file file.bak-$ts`) before editing them.

**Verify.** Resource back to baseline, service `active (running)`, path restored end-to-end with no collateral, query latency down / replication caught up, no new errors in the journal.

**Docs Delta.** If the fix changes anything documented in `<slug>/docs/` (instances, ports, access path), state the delta.
