# CI/CD playbooks

Scope: GitLab CI/CD pipelines, jobs, runners, artifacts/cache, variables, environments, and container registry (`glab`, `gitlab-runner`).

Risk mapping: pipeline status, job trace, runner status = L1. Job retry, pipeline cancel, runner pause/resume, cache clear = L2. CI/CD variable (secret) changes, runner registration, global CI config = L3.

## Pipeline failure triage
1. `glab ci list` — identify the failed pipeline and stage.
2. `glab ci trace <job-id>` — full job output.
3. Classify: build error (code), test failure (regression), infra error (runner/network), config error (`.gitlab-ci.yml`).
4. Infra errors → propose retry (L2). Code errors → report to the developer.
5. After retry, monitor the job/pipeline until completion.

## Runner troubleshooting
1. `glab ci runner list` — status (online/offline/paused). Verify the host is reachable.
2. Check `/etc/gitlab-runner/config.toml` — executor type (docker/shell/kubernetes).
3. Docker-in-Docker fails → check `privileged = true` and the Docker socket.
4. Resource exhaustion → check host CPU/memory/disk. Propose `docker system prune` (L3 on a shared host; see [container.md](container.md)).
5. Runner disappeared → check the registration token. Propose re-register (L3).

## Artifacts and cache
1. Check job trace for artifact upload errors. Verify size vs `artifacts:max_size`.
2. Stale dependencies → check `cache:key` strategy. Propose cache clear (L2).
3. Storage limits → check project/group usage. Propose artifact expiry policy (L2).

## Environments and deployment
1. `glab api projects/:id/environments` — protection rules, required approvals.
2. Rollback → find the last successful deployment, propose pipeline retry on that commit (L2).
3. Review apps → verify `environment:on_stop` cleanup actions.

## Pipeline optimization
1. Review `needs:` for DAG parallel execution. Identify sequential bottlenecks.
2. `glab ci list` — identify slowest jobs. Check for missing cache.
3. Deprecated `only/except` → recommend migration to `rules:`.
4. Duplicated CI config → propose shared templates via `include:`.

## Secret management
1. `glab variable list` — audit scope (project/group), protection, masking.
2. Check job traces for unmasked sensitive values. Propose masking (L2).
3. Flag variables not rotated in >90 days.

## Container registry
1. Check registry storage usage. Identify untagged/orphaned images.
2. Review cleanup policies for tag expiry.
3. Push/pull fails → verify `CI_REGISTRY_PASSWORD` and permissions.

## Pipeline best practices
- Use `rules:`, not `only/except` (deprecated).
- Use `needs:` for DAG pipelines.
- Use `include:` for shared templates from one central CI project.
- Set `interruptible: true` on MR pipelines.
- Protect prod deploys with environment protection rules.
- Never hardcode secrets; use CI/CD variables (masked + protected).
- Pin images by digest or exact version.

## Runner executor guide

| Executor | Best for | Isolation | Speed |
|---|---|---|---|
| Docker | General builds | Per-job container | Fast |
| Kubernetes | Cloud-native, autoscale | Per-job pod | Medium |
| Shell | Simple scripts (avoid in prod) | None | Fastest |
