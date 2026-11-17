# Linux troubleshooting

Scope: Linux host CPU, memory/OOM, disk capacity and I/O, systemd services, kernel, using the USE method.

## Risk levels for host actions

- **L1:** any read — `top`, `ps`, `free`, `df`, `ss`, `journalctl`, `dmesg`, `sar`, `systemctl status`, `cat /proc/*`.
- **L2:** `systemctl restart <svc>`, `kill` a runaway PID, `sysctl -w` (runtime), drop caches, logrotate, `renice`, `journalctl --vacuum-*`, add swap, `MemoryMax=` on a unit.
- **L3:** `reboot`, `systemctl disable`, persisted kernel params (`/etc/sysctl.conf` + apply), fstab edits, filesystem resize/`fsck`, `rm` on system paths, persisted OOM-killer tuning.

## Protocol

1. Observe: run the 60-second triage. Note what the tools do not show — absence redirects the hunt.
2. Analyze: localise to one resource (CPU / mem / disk / net / a service). Correlate timestamps across `dmesg`, `journalctl`, app logs.
3. Propose: Change Proposal with Host, Action, Blast radius, Rollback.
4. Act: snapshot state first (config copy, `systemctl show`, current `sysctl -a`).
5. Verify: resource back to baseline, service `active (running)`, no new errors in journal.

## 60-second triage (run first, in order)

```bash
uptime                          # load avg — 1/5/15 trend vs core count (nproc)
dmesg -T | tail -40             # OOM kills, disk errors, segfaults, link flaps
vmstat 1 5                      # r (runnable), b (blocked), si/so (swap), wa (io-wait)
free -h                         # mem + swap; "available" is the number that matters
df -h; df -i                    # disk full AND inode exhaustion
ss -s                           # socket summary — TIME-WAIT / orphan explosion
top -bn1 | head -20             # top CPU/MEM consumers
journalctl -p err -b --no-pager | tail -30   # boot-level errors
```

## USE method checklist

| Resource | Utilization | Saturation | Errors |
|---|---|---|---|
| CPU | `mpstat -P ALL 1`, `top` | load avg > cores, `vmstat` `r` col | `dmesg` MCE, throttling |
| Memory | `free -h`, `/proc/meminfo` | `si/so` in `vmstat`, OOM in `dmesg` | OOM killer, EDAC ECC |
| Disk (capacity) | `df -h`, `df -i` (inodes) | writes blocked, ENOSPC | `dmesg` I/O error, SMART |
| Disk (I/O) | `iostat -xz 1` `%util` | high `await`/`aqu-sz`, `wa` in vmstat | `iostat` errors, dmesg resets |
| Network | `sar -n DEV 1` | drops/overruns, TX queue | `ip -s link` errs, `netstat -s` |

## High CPU / high load

1. `top` → is load from `us` (user), `sy` (kernel), or `wa` (I/O wait)?
2. High `wa` → disk, not CPU → go to I/O wait.
3. High `sy` → syscall storm / context switches → `pidstat -w 1`, `strace -cp <pid>`.
4. High `us` → app hot loop → `pidstat 1`, `perf top -p <pid>` (if present).
5. Load high but CPU idle → threads in D state (uninterruptible, usually I/O/NFS): `ps -eo state,pid,cmd | grep '^D'`.

## OOM / memory pressure

1. `dmesg -T | grep -i -E 'oom|killed process'` — confirm the kill and which PID/cgroup.
2. `free -h` — `available` near zero? swap exhausted?
3. Who ate it: `ps aux --sort=-%mem | head`, or per-cgroup `systemd-cgtop`.
4. Cache vs RSS: high `buff/cache` is reclaimable (fine). A real leak is growing RSS.
5. Fix path: raise limit / add swap (L2), cap the offender with `MemoryMax=` in the systemd unit (L2), or tune app heap. Database engines must never swap → see [database.md](database.md) memory sections.
6. Kernel knobs (L3): `vm.overcommit_memory`, `vm.swappiness`, `oom_score_adj` per service.

Known pattern: acme-retail server crash (CPU + OOM).

## Disk full / ENOSPC

1. `df -h` full? Also `df -i` — inode exhaustion fails writes while `df -h` shows free space.
2. Biggest dirs: `du -x -d1 / 2>/dev/null | sort -rh | head` (repeat one level down).
3. Deleted-but-open files (space held until fd closes): `lsof +L1 | grep deleted` → restart the holder (L2).
4. Log floods: `journalctl --disk-usage`, `journalctl --vacuum-size=500M` (L2); enable logrotate.

## systemd service down

1. `systemctl status <svc>` → `Active:` state + last exit code/signal.
2. `journalctl -u <svc> -e --no-pager` → last lines before death.
3. `systemctl show <svc> -p Restart,RestartSec,ExecStart,MemoryMax` → restart policy sane?
4. Failed dependency: `systemctl list-dependencies <svc>`, `systemctl --failed`.
5. Exit codes: `signal=KILL` / `status=137` → OOM (go to OOM). `status=203` → EXEC: wrong path or permission on `ExecStart`.

## I/O wait / slow disk

1. `iostat -xz 1` → which device? `%util` near 100% + high `await` = saturated.
2. `pidstat -d 1` → which process does the I/O.
3. `iotop -o` (if present) for the live culprit.
4. Cloud disk (EBS / managed disk): check burst balance / IOPS credits → `ops-cloud`.

## Tooling

- Modern swaps: `ss` over `netstat`, `ip` over `ifconfig`/`route`, `journalctl` over tailing `/var/log`, `sar`/`pidstat` (sysstat) for history.
- Inventory a minimal host/container first:

```bash
for t in ss ip dig curl tcpdump iostat pidstat sar lsof; do command -v $t >/dev/null && echo "ok $t" || echo "MISSING $t"; done
```

## Upstream references

- USE Method Linux checklist: https://www.brendangregg.com/USEmethod/use-linux.html
- Linux performance analysis in 60s: https://netflixtechblog.com/linux-performance-analysis-in-60-000-milliseconds-accc10403c55
- Linux performance hub: https://www.brendangregg.com/linuxperf.html
