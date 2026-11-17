# Customer delivery (DOCX / PDF, SOW, sign-off)

Scope: turning a finished internal artifact (MoP, incident report, assessment, MoM) into a branded customer deliverable, writing a SOW, and the sign-off block. Brand rules: `docs/standards/ics-brand-guidelines.md` (headings **Instrument Sans**, body **Inter**, code **JetBrains Mono**).

Brand templates are not in git — fetch them with `python3 scripts/download_brand_assets.py` (`--category collateral` for the letterhead and SOW template).

## Two MoM/document templates, two jobs

| Template | Used by | For |
|---|---|---|
| `template/report-decks/mom-template.docx` (committed) | `doc_create_mom` (MCP) | the internal MoM written into `<slug>/mom/` |
| `template/collateral/ICS_Compute_Letterhead_Template_A4.docx` (downloaded) | `scripts/build_report_docx.py`, `scripts/format_docx_brand_kit.py` | client-facing `.docx` / `.pdf` export of any artifact |

## Export flow (explicit request only)

1. **Stage.** Copy the canonical `.md` to `/tmp/<slug>-customer.md`. The repo `.md` stays the internal source of truth.
2. **Sanitize with the native file edit tool** (`Edit` / `Write`) — never ad-hoc `python3 -c`, bash, `sed` or regex scripts. Read the staged file in full, then:
   - strip internal testing/demo notices ("for testing/example purposes only");
   - drop or rephrase internal repo housekeeping rows in `Schedule of Activity` ("update internal docs/runbooks", "update repo KB"), keeping row numbers sequential;
   - replace internal `.md` names and relative paths (`KB-*.md`, `tickets/*.md`, `access.md`, `../tickets/...`) with plain business language ("operational documentation", "prior ticket on 2026-09-18");
   - replace private GitHub issue URLs (`github.com/your-org/...`) with plain ticket identifiers;
   - for a `proposed` MoP, `## Result` reads `*Pending execution — to be recorded upon completion.*`.
3. **Generate DOCX:** `python3 scripts/build_report_docx.py /tmp/<slug>-customer.md -o <destination.docx>` — inherits the A4 letterhead and Example MSP Kit 2026 styling.
4. **PDF (if asked):** `libreoffice --headless --convert-to pdf --outdir <dir> <destination.docx>`.

Generated `.docx` / `.pdf` are never committed.

## Statement of Work (SOW)

**Path:** `<slug>/projects/<project>/SOW-YYYY-MM-DD-<slug>.docx`
**Template:** `template/collateral/Template SOW Example MSP Compute.docx` (downloaded, `--category collateral`).
**Required:** Project Background, Objectives, Scope of Work, Deliverables, Timeline, Exclusions, Customer Responsibilities, Pricing/Terms.

## Signature / sign-off block

For artifacts that need formal sign-off (incident report, MoP, MoM, assessment), or whenever the user asks for one. Signers are columns, attributes are rows, top-left cell empty:

```markdown
## Signature

| | Reported By | Acknowledged By |
|---|---|---|
| Date | YYYY-MM-DD | YYYY-MM-DD |
| Name | [Name] | [Name] |
| Position | [Position / Role] | [Position / Role] |
```

Three signers (MoP): `| | Prepared By | Reviewed By | Approved By |`.

`build_report_docx.py` renders the empty top-left cell as `Role / Sign` (white on `#BC1823`), centres the cells, bolds the first-column labels on `#F8F9FA`, and appends a `Signature` row with `( Digital Signature )` placeholders.
