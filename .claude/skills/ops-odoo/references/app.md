# Odoo Application (XML-RPC)

Inspect and troubleshoot business state through the external API: crons, mail, multi-company access, users.

## API access

- XML-RPC: `/xmlrpc/2/common` (`authenticate`, `version`) and `/xmlrpc/2/object` (`execute_kw`).
- JSON-RPC: `/jsonrpc`; authenticate via `common.authenticate()`.
- Read-only calls (`search`, `read`, `search_read`, `search_count`) are L1. `write`/`create`/`unlink` and button methods are L2/L3.

```python
import xmlrpc.client
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, api_key, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
models.execute_kw(db, uid, api_key, "ir.cron", "search_read",
                  [[["active", "=", True]]], {"fields": ["name", "nextcall", "lastcall"]})
```

## Scheduled actions (crons)

1. `search_read` on `ir.cron`: `active`, `nextcall`, `lastcall`.
2. `nextcall` in the past and not running -> check `pg_locks` for DB locks (see [infra.md](infra.md)).
3. Check Odoo logs for cron execution traces.
4. Manually triggering a cron is L2.

## Email system

1. `ir.mail_server`: SMTP host, port, encryption. `fetchmail.server` for incoming.
2. `search_read` on `mail.mail` with `state = exception` for stuck emails.
3. Check `mail.bounce.alias` and the catchall domain.

## Multi-company

1. `ir.rule` records for company-scoped access; verify `company_id` / `company_ids` on the records.
2. `res.users`: `company_ids` (allowed) and `company_id` (current).
3. Verify fiscal position mapping per company.

## Users

- Activate/deactivate a user (`res.users.active`) is L2.
- Access issues: check group membership, then `ir.model.access` and `ir.rule` (details in [module-dev.md](module-dev.md)).
