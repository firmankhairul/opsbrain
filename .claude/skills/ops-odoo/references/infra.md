# Odoo Infrastructure

Host access, service, logs, workers, PostgreSQL, backup/restore, version migration, proxy/SSL, and sizing.

## Access and service

- Reach the host via SSM (`aws ssm start-session --target <instance-id> --profile <p>`) or the SSH/bastion path in `<slug>/docs/access.md`.
- Service: `systemctl status odoo`, logs: `journalctl -u odoo` (or the `logfile` set in `odoo.conf`).
- Config lives in `odoo.conf`: `addons_path`, `workers`, `max_cron_threads`, `db_*`, `proxy_mode`.

## Performance / slow response

1. `top` / `free` on the host; `pg_stat_activity` on the DB for long-running queries.
2. Look for long-running cron jobs or heavy reports.
3. Propose worker count adjustment (L2) or database indexing.

## Module / application error

1. `journalctl -u odoo` for Tracebacks.
2. Identify custom addon vs core issue (path in the traceback).
3. Propose module upgrade (L2) or config fix; code fixes go through [module-dev.md](module-dev.md).

## Backup and restore

1. Verify the `pg_dump` schedule (cron/automated). Check filestore backup (`/var/lib/odoo/filestore/`).
2. Test restore on staging periodically. Watch backup file size trends.
3. If WAL archiving is enabled, verify `archive_command` and retention.
4. Restore execution is L3: approval plus downtime window.

## Version migration

1. Identify current and target version. Follow the official path one major at a time (14 -> 15 -> 16 -> 17 -> 18, never skip).
2. `pip list | grep odoo`, and check each custom addon `__manifest__.py` for compatibility.
3. Always run the migration on a staging copy first. Compare record counts pre/post.
4. Propose the migration plan (L3) with full rollback (DB snapshot + filestore backup).

## Proxy and SSL

1. Nginx: check `proxy_pass` and `proxy_set_header` for `X-Forwarded-*` (with `proxy_mode = True`).
2. Live channel: `/websocket` (v16+) or `/longpolling` (v15 and earlier), routed to the gevent port.
3. SSL: certificate validity, auto-renewal (certbot), HSTS headers.

## Architecture sizing

| Concurrent users | Setup | Workers |
|---|---|---|
| < 10 | 1 server (4 vCPU, 8 GB) | 2-4 |
| 10-50 | 1 server (8 vCPU, 16 GB) | 4-8 |
| 50-150 | App + DB separate | 8-12 |
| 150+ | 2 App + DB HA + PgBouncer | 16+ |

Formula: `workers = (vCPU x 2) + 1`, `max_cron_threads = 1-2`.

## PostgreSQL tuning (Odoo workload)

- `shared_buffers` = 25% of RAM
- `effective_cache_size` = 75% of RAM
- `work_mem = 64MB`
- `synchronous_commit = off` (safe performance boost)
- `log_min_duration_statement = 1000` (log queries > 1 s)
- Stuck crons or hung requests: check `pg_locks` joined with `pg_stat_activity`.
