# Odoo Module Development

Fix and extend custom addons (v16-v18) with minimal, regression-free changes.

## Workflow

1. Resolve `addons_path` from `odoo.conf`; read the module and the Traceback.
2. Back up any file before editing (`.bak`).
3. Root cause: Model vs View vs Controller.
4. Change Proposal: Module, Files, Patch Intent, Risk, Rollback.
5. Minimal patch -> `python -m py_compile <file>` -> upgrade: `odoo-bin -d <db> -u <module> --stop-after-init` (or restart with `-u`).
6. Verify logs and the feature as the target user role.

## Inheritance

- **Class** (`_inherit`): extend a model in place; adding fields/methods.
- **Prototype** (`_inherit` + `_name`): new model copying the parent. Use sparingly.
- **Delegation** (`_inherits`): composition via FK; extend without modifying the parent.
- **View** (`xpath`): inject/replace/modify view elements. Always specify `position`.

## Model best practices

- Use `@api.model_create_multi`, not single-record `create` (v16+).
- Computed fields that are searched or grouped: `store=True` with correct `@api.depends`.
- `_sql_constraints` for DB-level uniqueness.
- `ondelete="restrict"` on critical Many2one fields.
- Add a `company_id` field for multi-company support.

## Security

- **ir.model.access**: CRUD per model per group. Always create ACLs for new models.
- **ir.rule**: domain-based row-level security. Multi-company: `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`.
- **Group hierarchy**: `implied_ids` for inheritance; design to avoid privilege escalation.
- **sudo()**: bypasses access rules. Use sparingly and comment why.

## Migration scripts

- **pre-migrate**: before ORM update. Rename columns, back up data, drop constraints.
- **post-migrate**: after ORM update. Data transformation, populate new fields.
- **end-migrate**: after all modules. Cross-module data fixes.
- **OpenUpgrade**: `openupgradelib` for `rename_fields`, `rename_models`, `map_values`.

## Testing

- **TransactionCase**: standard; each test runs in a rolled-back transaction.
- **HttpCase**: controllers and web UI; `browser_js` for JS/tour tests.
- **Tagged**: `@tagged('post_install', '-at_install')` for lifecycle control.
- **Run**: `odoo-bin -d <db> --test-enable --stop-after-init -i <module>`.

## API and controllers

- JSON-RPC `/jsonrpc`, XML-RPC `/xmlrpc/2/common` and `/xmlrpc/2/object` (usage in [app.md](app.md)).
- REST controllers: `@http.route` with `type='json'` or `type='http'`, `auth='user'` or `auth='api_key'`.

## Performance

- `read_group()` for aggregations instead of `search()` + Python loops.
- Avoid `browse()` inside loops; it breaks ORM prefetch.
- SQL views: `_auto = False` model with `CREATE OR REPLACE VIEW` in `init()`.
- Profiling: `--limit-time-real=0` plus `ir.profile` or `py-spy`.

## OWL components (v16+)

- Register JS/CSS/SCSS in `__manifest__.py` under the `assets` key.
- OWL components live in `static/src/`.
- Debug with `?debug=assets` for unminified assets.
