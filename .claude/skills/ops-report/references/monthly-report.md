# Monthly Report Workflow

Scope: end-to-end workflow for the recurring monthly AWS customer report: registry, credential preflight, section-by-section markdown drafting, and PPT conversion after user approval.

Goal: customer-ready monthly AWS reports with consistent structure, business-readable narrative, and evidence-based recommendations mapped to AWS Well-Architected Framework (WAFR) pillars. Use it for recurring monthly customer reports, consistent reporting across multiple accounts/profiles, and account-based recommendations with approval labels.

## Repository layout

- Registry: `monthly-report/report-registry.yaml` (source of truth)
- Registry generator: `scripts/generate_monthly_report_customers.py`
- PPT template: `monthly-report/template/ICS_Compute_Deck_Template.pptx` (Example MSP Kit 2026; fetch with `python3 scripts/download_brand_assets.py`, gitignored). `Template.pptx` is the legacy deck, kept only for the `gen_ppt_final.py` method
- Per-customer recipes: `monthly-report/custom/<slug>/`
- Output: `monthly-report/output/<slug>/<YYYY-MM>/` — **markdown only**
- PPT generator: `scripts/generate_ppt.py <slug> <YYYY-MM>` (see [PPT tooling](#ppt-tooling))

`<slug>` is identical to the customer folder name at the repo root and to the `folder:` key in that customer's `customer.yaml`. Never invent a variant.

Generated `.pptx` and `.docx` are never committed; `.gitignore` blocks both. Deliver them from the working directory and let them stay untracked.

## 1. Customer registry first

Before collecting AWS data, read `monthly-report/report-registry.yaml`.

1. Process only customers with `monthly_report.enabled: true`.
2. Default report scope is one combined report per customer when `monthly_report.report_mode: combined`.
3. Process only accounts with `include: true`.
4. For specific per-account requests, select only the requested account/profile and use per-account output naming.
5. For multi-region accounts, collect each region listed in `accounts[].regions` and summarize under the same account section.
6. Skip entries under `skipped_customers`.
7. For customers where `report_template: custom`, read `monthly_report.custom_data_collection` before collecting any data. If the file is missing, stop and ask for the custom collection instructions.
8. Never infer a customer from profile name alone when the registry marks it as unmapped.
9. If the registry is stale or missing, propose running `python3 scripts/generate_monthly_report_customers.py --output monthly-report/report-registry.yaml` before generating reports.

Explicitly skipped until custom data collection examples are provided: **acme-retail**, **acme-retail**.

### Customer not in registry

If the user requests a monthly report for a customer not in the registry:

1. Look up the customer via the `get_customer` MCP tool (reads `customer.yaml`) to get account info.
2. Detect the auth method by reading `~/.aws/config` for each profile:

```
Profile has sso_session = X  →  method: sso_session
                                  login_command: aws sso login --sso-session X

Profile has sso_start_url   →  method: sso_profile
  but no sso_session            login_command: aws sso login --profile {profile}

Profile exists, no SSO      →  method: aws_login
                                  login_command: aws login --profile {profile}

Profile not found            →  method: not_configured
                                  login_command: null
```

3. Add it to `monthly-report/report-registry.yaml` without asking — just add and confirm:

```yaml
- slug: {customer.folder}
  name: {customer.display_name}
  monthly_report:
    enabled: true
    report_mode: combined
    report_template: default
    output_name: {customer.folder}
  accounts:
    - name: {purpose}
      profile: {account.profile}
      account_id: "{account.id}"
      regions:
        - {account.region}
      primary_region: {account.region}
      role: {account.role}
      include: true
      auth:
        method: {detected_method}
        sso_session: {sso_session or null}
        login_command: {detected_login_command}
        credential_check: aws sts get-caller-identity --profile {account.profile}
```

4. Tell the user (in their language) that the customer was missing from the registry, has been added with the default template and the detected auth method, and that generation is continuing.
5. Proceed with report generation immediately.

If `customer.yaml` also does not exist for that customer: stop and ask the user for account details before adding to the registry.

## 2. Custom data collection

When a registry customer uses `monthly_report.report_template: custom`:

1. Read the path in `monthly_report.custom_data_collection` first.
2. Check `monthly_report.sample_path` for prior reports or examples before writing the new report.
3. Follow the custom notes over the default data collection commands where they conflict.
4. Preserve the custom report's current content, section names, ordering, and business meaning unless the user explicitly asks for content changes.
5. Use the Example MSP visual template for cleanup only: cover, header/footer branding, readable typography, tables, and slide spacing. Do not force the default section structure onto custom reports.
6. Use the default 11-section structure only when the custom sample/instructions do not define a different structure and the user explicitly asks for a new report structure.

acme-retail custom setup:

- Instruction file: `monthly-report/custom/acme-retail/data-collection.md`
- Sample folder: `monthly-report/custom/acme-retail/sample/`
- Cost and usage source: CUR from `prod-root`

## 3. Credential preflight

Before collecting report data, validate credentials for every included account:

```bash
aws sts get-caller-identity --profile <profile>
```

If credentials are missing or expired, respond with the registry-defined login command and stop collection for that account.

| `auth.method` | Action |
|---|---|
| `sso_session` | `aws sso login --sso-session <session>` — one login covers every profile on that session |
| `sso_profile` | `aws sso login --profile <profile>` |
| `aws_login` | `aws login --profile <profile>` |
| `direct_static` | Do not suggest SSO; ask the operator to refresh the static credential and rerun `credential_check` |
| `unknown` / `not_configured` | Skip the account and request registry/profile metadata cleanup |

Do not run broad AWS collection if any requested account fails preflight, unless the user explicitly approves a partial report.

## 4. Required inputs

| Input | Format | Example |
|-------|--------|---------|
| `period_start` | YYYY-MM-DD | 2026-04-01 |
| `period_end` | YYYY-MM-DD (exclusive) | 2026-05-01 |
| `month_label` | Month Year | April 2026 |
| `customers` | registry slug/name(s) | bsp, programa, acme-retail |
| `profiles` | AWS profile name(s), from registry | bsp, programa, acme-retail-prod |
| `region` | AWS region, from registry unless overridden | ap-southeast-3 |

## 5. Output path

```
monthly-report/output/<slug>/<YYYY-MM>/
  monthly-report-<slug>-<mon>-<year>.md     # Primary: AI-generated draft, user verifies
  monthly-report-<slug>-<mon>-<year>.pptx   # Customer-facing: only after user approves the .md; never committed
```

Example: `monthly-report/output/example-a/2026-08/monthly-report-example-a-aug-2026.md`.

Service Screener output (optional, per customer, not required for the monthly report) lives under `monthly-report/service-screener/`.

## 6. Drafting workflow

1. Create the skeleton. `doc_create_monthly_report(customer, period)` writes `<slug>/monthly-report/monthly-report-YYYY-MM.md` with `> **TODO**` markers and a period end hardcoded to `-30`. Move it to the output path above, fix the period line, and keep the `> TODO` markers — or write the skeleton from [monthly-markdown-structure.md](monthly-markdown-structure.md) directly.
2. Collect and write each section one at a time, using [monthly-data-collection.md](monthly-data-collection.md). Update the file after each section, not at the end.
3. Mark each section `> Done` when complete, `> Limited — {reason}` if access was denied (see [monthly-wafr-and-writing.md](monthly-wafr-and-writing.md)).
4. Pull "Tickets This Period" from `<slug>/tickets/` for the period.
5. After all sections: tell the user the draft is complete and ask them to review before converting to PPT.
6. User verifies, edits if needed, then explicitly asks to convert ("convert ke PPT") — build the PPT from the verified `.md` per [monthly-ppt-conversion.md](monthly-ppt-conversion.md) and [monthly-slide-structure.md](monthly-slide-structure.md).

Never batch all sections into one write. Never generate `.pptx` without explicit user approval. Never re-collect AWS data during conversion.

## Reference files

Read each only when you reach the step that needs it.

| File | Read it when |
|---|---|
| [monthly-data-collection.md](monthly-data-collection.md) | Collecting AWS data. Every CLI command, per service. |
| [monthly-wafr-and-writing.md](monthly-wafr-and-writing.md) | Mapping findings to WAFR pillars; writing rules and section status markers. |
| [monthly-markdown-structure.md](monthly-markdown-structure.md) | Writing the markdown report: the section-by-section skeleton. |
| [monthly-slide-structure.md](monthly-slide-structure.md) | Building a `report_template: default` deck: 12-slide order and design spec. |
| [monthly-deck-rules.md](monthly-deck-rules.md) | Example MSP Kit 2026 presentation rules, layout mapping, and review checklist. |
| [monthly-ppt-conversion.md](monthly-ppt-conversion.md) | Converting markdown to PPT, plus the pre-delivery quality checklist. |

## PPT tooling

Markdown is always first: the user verifies the `.md`, then explicitly asks for the PPT.

| Case | Command | Notes |
|---|---|---|
| Any customer | `python3 scripts/generate_ppt.py <slug> <YYYY-MM>` | Renders the single `monthly-report-*.md` in `monthly-report/output/<slug>/<YYYY-MM>/` onto the Example MSP Kit deck and writes the `.pptx` next to it (gitignored). `--md`, `-o`, `--template` override. Nothing runs on import or `--help`. |
| Customer with a polished previous-month deck (BSP, acme-retail, EXAMPLE, acme-retail, acme-retail, acme-retail, acme-retail) | method in [monthly-ppt-conversion.md](monthly-ppt-conversion.md), script `scripts/gen_ppt_final.py` | Legacy June 2026 batch: customers and paths are hardcoded and it creates its output folder on import. Use only when the customer's own previous deck must be the base. |

What `generate_ppt.py` does with the draft:

- **Slide order is the draft's order.** The author decides the sections; the script renders them. Cover (from the draft's cover lines: customer name, period) and Thank You come from the kit; `## Thank You` and empty sections in the draft are not rendered. A `## Document Acceptance` with no table gets the standard sign-off table.
- **`report_template: default`** customers (registry) also get the 3-box Executive Summary (summary, key figures, top recommendations): one slide when it fits at 9 pt, otherwise two slides. **`custom`** customers keep their layout; the deck is only restyled.
- **Long tables and text paginate** with a `(cont.)` title; a heading or a trailing `Label:` is never left alone at the bottom.
- **No emoji, ever.** Ratings become words (GOOD / FAIR / NEEDS WORK); see `scripts/report_text.py`.
- Instrument Sans, Semibold at most, `#BC1823` table headers, 0.58 in safe margin, two-digit numbers on content slides only.

The kit has no "Example MSP Clients" logo slide; a draft section by that name is rendered only if it has content.

Always render the result to PNG and look at it before delivery (checklist in [monthly-ppt-conversion.md](monthly-ppt-conversion.md)).
