# Container playbooks

Scope: standalone Docker / docker compose hosts without Kubernetes (`docker`, `docker compose`, `docker inspect`, `dmesg`, `ctr`). Pods in a cluster belong in [kubernetes.md](kubernetes.md).

Risk mapping:
- L1: `docker ps -a`, `docker logs`, `docker inspect`, `docker stats`, `docker network/volume ls|inspect`, `docker events`, `dmesg`.
- L2: `docker restart`, `docker compose up -d`, `--memory`/`--cpus` limits, `docker network connect`, adding HEALTHCHECK/restart policy, log-rotation config.
- L3: `docker rm -f`, `docker volume rm`, `docker system prune`, `docker network prune`, image repull that drops a running tag, daemon.json edit + `systemctl restart docker` (restarts ALL containers). `volume rm` / `prune` = data loss: confirm no bind mount holds live data and snapshot the volume first. Change Proposal must name host, affected containers, and data-loss risk.

## 4-step evidence pull (always, in order)

Answer three questions: was the container created? did PID 1 start? did something outside kill or block it?

```bash
docker ps -a                           # 1. status + EXIT CODE
docker logs --tail 100 <c>             # 2. what PID 1 said before dying
docker inspect <c>                     # 3. .State (OOMKilled, ExitCode, Error), Mounts, Config
docker run -it --entrypoint sh <img>   # 4. interactive repro of the image
```

Then classify: startup vs crash vs OOM vs network vs volume vs image. One suspect at a time.

## Exit code cheat sheet

| Code | Meaning | First check |
|---|---|---|
| 0 | Clean exit | Foreground process finished; must be long-running / daemonized |
| 1 | General app error | `docker logs`; pattern-match message (below) |
| 125 | Docker daemon/run error | Bad flag, image not found, daemon issue |
| 126 | Command not executable | Permission / not a binary |
| 127 | Command not found | Wrong `CMD`/`ENTRYPOINT` path, missing binary in image |
| 137 | 128+9 = SIGKILL | OOM (cgroup or host) or external kill; disambiguate below |
| 139 | 128+11 = SIGSEGV | Native crash (C/C++), bad lib, arch mismatch |
| 143 | 128+15 = SIGTERM | Graceful stop / orchestrator asked it to stop |

Exit 1 pattern-match: `No such file` → mount/config path. `port already allocated` → port conflict. `Permission denied` → file perms / SELinux. `Connection refused` → dependency not ready.

## OOMKilled / exit 137
Host-level OOM analysis continues in the `ops-troubleshoot` skill.
1. `docker inspect <c> --format '{{.State.OOMKilled}} {{.State.ExitCode}}'`.
2. `OOMKilled=true` → cgroup killed PID 1: raise `--memory` or fix the leak.
3. `OOMKilled=false` but exit 137 → external SIGKILL: `dmesg -T | grep -i oom` (host OOM), stop-timeout escalation, `docker kill`, or CI/systemd killing the scope.
4. Multi-process trap: supervisord/shell-wrapper containers → kernel may OOM a child while PID 1 lives. `OOMKilled=false`, container runs degraded; only trace is `memory.events` in the cgroup. Prefer one process per container.
5. Gotchas: `--memory` without `--memory-swap` sets swap to 2x. Java `-Xmx` must be < `--memory`. cgroups v2 ignores `--oom-kill-disable`.
6. Prevent by trend: a container at 60% memory growing 5%/hr OOMs in ~8h. Alert on slope, not level.

## Container won't start / restart loops
1. `docker ps -a` exit code → jump to the matching tree via the cheat sheet.
2. Empty `docker logs` + instant exit → PID 1 never started: bad `ENTRYPOINT`/`CMD` (127), or foreground process exiting (0).
3. Isolate by subtraction: run without volumes, then without custom network, then with minimal env; add back until it breaks.
4. Restart storm → `docker inspect` `.RestartCount` + `.State.Error`; set restart policy `unless-stopped`.

## Networking (container to container / outside)
1. `docker network ls` + `docker network inspect <net>` → are the containers on the same user-defined network? Default bridge has no DNS-by-name.
2. Name resolution between containers works only on a user-defined network via embedded DNS `127.0.0.11`. On default bridge → use a compose/user-defined network (`--link` is legacy).
3. Port not reachable from host → `-p host:container` present? `docker port <c>`. App bound to `127.0.0.1` inside → must bind `0.0.0.0`.
4. Outbound broken → container `/etc/resolv.conf`, then host firewall/NAT (`iptables` MASQUERADE), then upstream (hand off to the `ops-troubleshoot` skill).

## Volume / data issues
1. `docker inspect <c> --format '{{json .Mounts}}'` → named volume or bind mount? Path correct?
2. Permission denied on mount → UID/GID mismatch between host dir and container user, or SELinux → add `:z`/`:Z` to the mount.
3. "Data disappeared on restart" → app wrote to the container layer, not the volume path. Verify the volume target matches where the app writes.
4. Docker Desktop: bind mounts cross a VM boundary (slow, different semantics) → prefer named volumes.

## Verify after a change
`docker ps` healthy, HEALTHCHECK passing, logs clean, `docker stats` memory stable over time.

## Preventive baseline
- `HEALTHCHECK` in the image, restart policy `unless-stopped`, log rotation (`max-size` + `max-file` in daemon.json), resource limits (`--memory`, `--cpus`), `docker stats`/Prometheus alerting.
- Single process per container so OOM shows as `OOMKilled:true` and the restart policy fires.
- Docker Engine 29: default `nofile` ulimit dropped 1048576 → 1024; override with `--ulimit nofile=` if connection pools/servers depend on the old default.

## External references
- Exit code 137 (OOM vs SIGKILL): https://www.netdata.cloud/guides/docker/docker-exit-code-137/
- OOMKilled causes/detection/prevention: https://www.netdata.cloud/guides/docker/docker-oomkilled/
- Container startup troubleshooting: https://devops.aibit.im/en/article/troubleshooting-docker-container-startup-issues
- Docker runtime metrics / limits: https://docs.docker.com/config/containers/runmetrics/
