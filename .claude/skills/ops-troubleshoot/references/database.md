# Database troubleshooting

Scope: MySQL/MariaDB, PostgreSQL and Redis engine-level diagnosis — slow queries, locks, replication lag, memory and connections. Read the engine's own instrumentation before touching config; a query fix beats a hardware upgrade.

## Risk levels for database actions

- **L1:** `SELECT` on `performance_schema` / `information_schema` / `pg_stat_*`, `SHOW PROCESSLIST`, `SHOW ENGINE INNODB STATUS`, `EXPLAIN`, `redis-cli INFO`, slow-log reads. On MySQL 8.0 < 8.0.40, poll `data_locks` sparingly (see Lock contention).
- **L2:** `KILL <query_id>`, `pg_terminate_backend` / `pg_cancel_backend`, online `CREATE INDEX` (`ALGORITHM=INPLACE`), `ANALYZE`/`VACUUM`, dynamic `SET GLOBAL`, `redis-cli CONFIG SET`.
- **L3:** `ALTER` with table rewrite/lock, `DROP`, engine restart, failover / promote replica, persisted `innodb_buffer_pool_size` + restart, buffer-pool resize, `FLUSHALL`, skipping a replication error. Confirm a backup exists first.

## Protocol

1. Observe: processlist + slow log + engine status. Snapshot current global variables before proposing tuning.
2. Analyze: slow query vs lock vs replication vs memory vs connection exhaustion — one category at a time.
3. Propose: Change Proposal with Instance, Action, Lock/blast risk, Rollback, Backup confirmation.
4. Act: DDL on large prod tables → `pt-online-schema-change` or `gh-ost`.
5. Verify: query latency down, no new locks, replication caught up, memory stable.

## MySQL / MariaDB

### Slow query hunt

```sql
-- Rank by average latency (digest = normalized query); timers are picoseconds
SELECT DIGEST_TEXT, COUNT_STAR, AVG_TIMER_WAIT/1e9 AS avg_ms,
       SUM_TIMER_WAIT/1e12 AS total_s, SUM_ROWS_EXAMINED, SUM_ROWS_SENT
FROM performance_schema.events_statements_summary_by_digest
ORDER BY AVG_TIMER_WAIT DESC LIMIT 15;

-- Post-mortem of recent statements (raise history size if too shallow)
SELECT * FROM performance_schema.events_statements_history ORDER BY TIMER_START DESC;
```

- `EXPLAIN <query>` → look for `type=ALL` (full scan), `Using filesort`, `Using temporary`.
- High `ROWS_EXAMINED : ROWS_SENT` ratio = missing or ineffective index.
- Slow-log fallback: `slow_query_log=1`, `long_query_time=1`. Rank by Count × Time (total cost), not per-run time.

### Lock contention

```sql
SHOW ENGINE INNODB STATUS\G                         -- LATEST DETECTED DEADLOCK + lock waits
SELECT * FROM performance_schema.data_lock_waits;   -- who waits on whom
-- MariaDB metadata locks (DDL blocked by a long transaction):
SELECT * FROM information_schema.metadata_lock_info;
```

- MySQL 8.0 before 8.0.40: polling `data_locks` / `data_lock_waits` every few seconds under load can take a global InnoDB mutex and freeze all transactions (bug #111082). Query once, not in a loop.
- Deadlock fix: consistent lock ordering, shorter transactions, batch big writes (`LIMIT 1000`), correct indexes.

### Replication lag

```sql
SHOW REPLICA STATUS\G   -- SHOW SLAVE STATUS on older versions → Seconds_Behind_Source
```

- `Replica_IO_Running` and `Replica_SQL_Running` must both be `Yes`.
- `Seconds_Behind_Source` growing → single-threaded apply? enable `replica_parallel_workers`.
- SQL thread errored → read `Last_SQL_Error`. Skipping is L3 (data-divergence risk).

### Memory / OOM

Pairs with the OOM section in [linux.md](linux.md).

- `innodb_buffer_pool_size` ≈ 60–70% of RAM on a dedicated host; leave headroom — per-connection buffers come on top.
- Per-connection cost ≈ (`read_buffer_size` + `sort_buffer_size` + `join_buffer_size` + tmp table) × `max_connections`. Blows up in connection storms.
- Set `vm.swappiness=1`; InnoDB must never swap.
- Connections: `SHOW STATUS LIKE 'Threads_connected';` vs `SHOW VARIABLES LIKE 'max_connections';`.

## PostgreSQL

### Slow queries

```sql
SELECT query, calls, mean_exec_time, total_exec_time, rows
FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 15;   -- needs the extension
EXPLAIN (ANALYZE, BUFFERS) <query>;                               -- real timing + buffer hits/reads
```

`EXPLAIN ANALYZE` executes the query — wrap writes in `BEGIN; ... ROLLBACK;`.

### Locks and bloat

```sql
SELECT * FROM pg_locks l JOIN pg_stat_activity a USING (pid) WHERE NOT granted;   -- blocked
SELECT pid, state, wait_event_type, query, now()-query_start AS dur
FROM pg_stat_activity ORDER BY dur DESC;                                          -- long runners
```

- `idle in transaction` sessions holding locks → set `idle_in_transaction_session_timeout`.
- Autovacuum falling behind → table/index bloat and txid wraparound risk. Check `pg_stat_user_tables.n_dead_tup`.
- `pg_cancel_backend(pid)` cancels the query only; `pg_terminate_backend(pid)` kills the session (both L2).

## Redis

```bash
redis-cli INFO memory        # used_memory vs maxmemory, mem_fragmentation_ratio
redis-cli INFO stats         # keyspace_hits/misses, evicted_keys
redis-cli --bigkeys          # memory hogs
redis-cli SLOWLOG GET 25     # slow commands
```

- `evicted_keys` rising → `maxmemory` too low or wrong `maxmemory-policy` (`allkeys-lru` for a cache).
- Never `KEYS *` on prod — O(N) blocks the single thread; use `SCAN`.
- Latency spikes → check `LATENCY DOCTOR` / latency monitor, tune RDB/AOF fsync, watch fork time on save.

## Upstream references

- MySQL slow log + Performance Schema: https://www.databasejournal.com/mysql/troubleshooting-mysql-performance-issues-using-the-slow-log-and-performance-schema/
- MariaDB `events_statements_history`: https://mariadb.com/kb/en/performance-schema-events_statements_history-table/
- MySQL bug #111082 (data_locks stall, fixed 8.0.40): https://bugs.mysql.com/bug.php?id=111082
- PostgreSQL `pg_stat_statements`: https://www.postgresql.org/docs/current/pgstatstatements.html
