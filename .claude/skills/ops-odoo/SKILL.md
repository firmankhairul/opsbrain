---
name: ops-odoo
description: >-
  Operate, troubleshoot, and develop Odoo ERP systems: server and database
  infrastructure (SSH/SSM, service, PostgreSQL, workers, logs), application
  state over XML-RPC, and custom addon development. Use when the task mentions
  Odoo, ERP, odoo-bin, odoo.conf, workers, max_cron_threads, longpolling or
  websocket, filestore, Odoo backup/restore or version migration, XML-RPC or
  JSON-RPC, ir.cron scheduled actions, mail queue, multi-company rules, or a
  custom addon/module: model, field, view, xpath, ACL, ir.rule, controller,
  OWL component, assets, read_group, migration script, tests, or upgrading a
  module (-u).
metadata:
  version: "4.0.0"
  replaces: "ops-odoo odoo-dev"
---

# Odoo Operations and Development

Keep Odoo servers healthy, diagnose application issues, and ship safe fixes to custom modules (v14-v18).

## Engagement rules

- Enter through `ms-ops`: it resolves the customer, the profile, and reads `<slug>/docs/`. If this skill is invoked directly, call `get_customer` and read the customer docs before touching the account.
- Risk levels: **L1** read-only (Describe/List/Get, metrics, logs) runs without asking. **L2** scoped or reversible change needs a Change Proposal and explicit approval. **L3** destructive or wide blast radius needs an explicit warning, a Change Proposal, a Rollback Plan, and approval.
- Never guess a profile, account, subscription, or project. If ambiguous, ask one targeted question.
- Expired session: stop and return the exact login command; do not retry.
- Output contract: `Current State`, `Findings`, `Risk/Impact`, `Change Proposal`, `Rollback`, `Verification`, `Docs Delta` (drop proposal/rollback when read-only).

## Pick the reference

Read only the file you need.

| Topic | Read | When |
|---|---|---|
| Infrastructure | [infra.md](references/infra.md) | Host access, service, logs, slowness, workers, PostgreSQL, backup/restore, version migration, proxy/SSL, sizing |
| Application | [app.md](references/app.md) | XML-RPC/JSON-RPC inspection, crons, mail queue, multi-company access, users |
| Module development | [module-dev.md](references/module-dev.md) | Changing a custom addon: models, views, security, migration scripts, tests, controllers, OWL, performance |

## Common method

Two modes: **INFRA** (server, logs, database) and **APP/DEV** (business data via XML-RPC, addon code).

1. **Observe (L1):** Odoo logs, host metrics, `pg_stat_activity`; XML-RPC `search`/`read` for app state; read module code after resolving `addons_path`.
2. **Analyze:** Correlate server logs with the failing business workflow. Classify root cause: infra vs core vs custom addon; for code, Model vs View vs Controller.
3. **Propose (L2/L3):** Change Proposal states Mode (INFRA/APP/DEV), Action or Patch Intent, Target (host/db/module + files), Risk, Rollback.
4. **Act:** Only after approval. Minimal fix, `python -m py_compile` on touched files, then upgrade the module.
5. **Verify:** Service health, no new Tracebacks in the log, functional check as the affected user role.

Domain safety rules:

- Back up before any direct file edit (`cp file file.bak`) and before any DB-affecting change (`pg_dump` + filestore).
- Risk mapping: L1 = `systemctl status`, log tail, XML-RPC reads, code reading, syntax checks, creating backups. L2 = service restart, worker tuning, cron trigger, activate/deactivate user, code patch, view/ACL change, module upgrade. L3 = module uninstall, bulk record delete, database drop/restore, model change touching production data, production deployment or version migration.
- Never run a production migration or restore without a tested staging run and a downtime window.
