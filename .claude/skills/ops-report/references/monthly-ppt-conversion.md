# Monthly Report: PPT Conversion and Quality Checklist

Scope: converting a user-verified monthly markdown report into the customer PPT, plus the pre-delivery checklist. Slide order and design spec live in [monthly-slide-structure.md](monthly-slide-structure.md).

## PPT Conversion

When user says "convert ke PPT" or "jadiin PPT":

### Standard method: `generate_ppt.py` renders the verified `.md` onto the Example MSP Kit

`python3 scripts/generate_ppt.py <slug> <YYYY-MM>` is the default for every
customer. It reads the single `monthly-report-*.md` in the output folder and
renders it onto the Example MSP Kit deck. The markdown is the source; the script owns
layout. The layout rules below are **fixed and consistent across all customers**
so every monthly deck comes out in the same shape — do not re-implement them
per customer.

Auto-layout the script guarantees (in `render_blocks`):

- **Tables are never split across slides.** Each table is rendered whole on one
  slide; the font shrinks (9 pt → 5 pt floor) only when needed to fit. A table
  too tall for the current slide moves whole to the next slide.
- **A table's title heading stays on the same slide as its table** — a `### ...`
  immediately followed by a table is kept together.
- **A heading groups with its paragraphs/bullets into one text block** that is
  never split mid-item; wrapped list-item continuation lines are joined, not
  orphaned. Groups shrink (10 pt → 7 pt floor) rather than break.
- **No emoji, ever** (ratings become GOOD / FAIR / NEEDS WORK via
  `report_text.py`); markdown artifacts are stripped; `↑↓` → `+/-`.

### Per-customer deck shaping: `monthly-report/custom/<slug>/deck-prefs.yaml`

Optional file, read automatically by `generate_ppt.py`. It records durable
deck-shaping choices so a customer's deck always comes out the same way and
manual edits never have to be redone. Keys:

```yaml
# render all heading+items groups of a section in ONE text box on one slide
merge_sections:
  - Service Portfolio
  - Prioritised Action Plan   # acme-retail: keep the whole action plan on one slide

# show ONLY tables (and each table's title) for a section; drop surrounding prose
tables_only_sections:
  - Cost Summary

# slides that are NOT in the markdown, inserted by the generator (front-matter etc.)
extra_slides:
  - title: Document Information
    position: 2            # 1-based; 2 = right after the cover
    intro:                 # paragraph lines above the tables (optional)
      - "Client   : Example Corp"
    tables:                # each: optional heading + header row + rows
      - headers: [Version, Date, Prepared By, Description]
        rows:
          - ["2.0", "30 September 2026", "Example MSP Compute", "Initial Version"]
      - heading: Distribution List
        headers: [Name, Organization, Email]
        rows:
          - ["Dani Nugraha", "Example Corp", "contact@example.com"]

# drop specific paragraphs/notes wherever they appear (leading-substring match,
# tolerant of *emphasis*); a safety net for notes that should never reach the deck
suppress:
  - "Based on monthly operational telemetry. Not a formal AWS Well-Architected Review"
```

Section titles in `merge_sections` / `tables_only_sections` match **exactly OR by
prefix** (`title_matches` in `generate_ppt.py`). So list the stable stem without a
month suffix: `Prioritised Action Plan` matches `Prioritised Action Plan — October
2026`, `... November 2026`, and so on — the rule keeps working each month without
editing the prefs. A `merge_sections` section renders as a single shrink-to-fit text
box (font 10 → 6 floor) and is never flowed onto `(cont.)` slides.

`extra_slides` inserts operator-authored slides that are **not** in the markdown — a
Document Information / front-matter page, a distribution list, an acceptance table.
Each entry is `title` + optional `intro` lines + optional `tables` (heading +
headers + rows), moved to its 1-based `position` (closing "Thank You" always stays
last). The slide uses the kit's content base (eyebrow, number, background), so it
looks native. Keep each extra slide to about one screen — it does not paginate. Record
such a slide here once (e.g. when the operator adds it by hand) and the generator
reproduces it every month, so a manual addition never has to be redone.

Keep the markdown itself clean and aligned to the intended deck — `deck-prefs.yaml`
shapes/omits, it does not rewrite content. When the operator deletes slides or
trims prose by hand, record the intent here AND fix the `.md` so the two match.

### Legacy method: copy each customer's OWN polished previous-month PPT

Use only when a customer's own previous polished deck must be the visual base
(the June 2026 batch below). Everything else uses `generate_ppt.py` above.

Script: `scripts/gen_ppt_final.py` (repo root; legacy June 2026 batch with hardcoded customers). Method:
1. `shutil.copyfile(prev_month_polished_pptx, out)` — inherits ALL design
   (background, Example MSP logo, PREMIER PARTNER badge, table styling, centered titles).
2. Replace content BY ROLE (shape names are unstable "Google Shape;NNN"):
   dispatch per slide on its TITLE text; fill tables in document order; replace
   non-title text shapes. Helpers: `slide_title_text`, `slide_tables`,
   `slide_bodies`, `fill_table`, `set_shape_text` (must `tf.clear()` first).
3. NEVER build slides from scratch (loses background/logo) or clone slide XML
   (duplicate media parts → corrupt file that won't open).

**Design source = last month's polished deck per customer**, kept locally in
`monthly-report/output/<slug>/<YYYY-MM>/` (never committed — `.pptx` is ignored):
- acme-retail: `monthly-report-bintang-bali-indah-may-2026.pptx`
- BSP: `Monthly Report Bakrie Sumatera Plantation Period May 2026.pptx`
- acme-retail: `monthly-report-acme-retail-may-2026.pptx`
- EXAMPLE: `Monthly Report EXAMPLEndonesia May 2026.pptx`
- acme-retail: `Monthly Report acme-retail Period May 2026.pptx`
- acme-retail: `Monthly Report acme-retail-May 2026.pptx`
- acme-retail: `Monthly Report acme-retail - May 2026.pptx`

### Per-customer layout differs — adapt

- Exec Summary table: 2-col Metric|Value (BSP/EXAMPLE/acme-retail), 3-col Total|MoM|Budget
  (acme-retail), or no table (acme-retail). Branch on column count.
- Service Portfolio = 7x3 table (not a bullet list).
- acme-retail: Scope 9x3, per-account cost 11x4 x2 + 3x4, Security/GuardDuty/IAM text,
  Requirements 9x4. Per-account + master-service tables live in `## Usage Summary`.
- acme-retail: numbered section titles ("2. Executive Summary") use smaller font — detect
  section header by mid-size font, not the 250000 big-title threshold.

### CRITICAL gotchas

1. Emoji regex must use 8-hex `\U0001F504`, NEVER 4-hex `\u1F504` (the latter
   deletes every digit `4` from cost figures). Verify numbers after cleaning.
2. No emoji anywhere in a report. WAFR ratings are the words GOOD / FAIR / NEEDS WORK; `scripts/report_text.py` (used by `generate_ppt.py` and `build_report_docx.py`) also turns a symbol-only cell into a word and drops symbols inside text. Do not write emoji in the draft in the first place.
3. `tf.clear()` before writing text (leftover empty paragraphs spread content).
4. Theme/scheme-color cells (fill=None) render dark-on-dark → force light
   (DDDDDD) when a cell/run has no explicit RGB color.
5. Strip markdown: `##`, `**`, `` ` ``, `---`, `>` blockquotes; `↑↓`→`+/-`.
6. Fill scope/metric tables with the CUSTOMER's own data (borrowed bases list the
   wrong customer's accounts).
7. Tables have FIXED rows in the reference — DELETE surplus rows so each table
   fits the actual finding count (no blank filler / leftover reference rows that
   look like blind copy-paste). `fill_table` trims to header + non-empty rows.

### MANDATORY verification — always LOOK, never trust XML/logs

```
libreoffice --headless -env:UserInstallation=file:///tmp/lo --convert-to pdf --outdir /tmp <pptx>
pdftoppm -png -r 62 -f 5 -l 15 /tmp/<name>.pdf /tmp/pg
```
Read the PNGs. PDF conversion success proves it opens; PNG proves it looks right.

Do NOT re-collect AWS data — use only the verified `.md` file.

## Quality Checklist

- [ ] Period and account identity correct
- [ ] Executive Summary: one narrative paragraph + Approval Status + Top Recommendations
- [ ] Service Portfolio: domain list only, no tables
- [ ] Cost Summary: top 10 table with MoM delta column, EC2 breakdown, EC2 other breakdown
- [ ] Utilization: only sections for services that exist in the account
- [ ] Security: narrative + visibility limitations at the end
- [ ] WAFR: all 6 pillars with status emoji + disclaimer line
- [ ] Recommendations: sorted HIGH first, every row has Est. Impact
- [ ] Cost Optimization Opportunities: present only if idle/waste resources found
- [ ] Tickets This Period: pulled from `{customer}/tickets/` for the period, omitted if none
- [ ] Pending Validation: narrative only, no tables
- [ ] Output path: `monthly-report/output/{slug}/{YYYY-MM}/monthly-report-{slug}-{mon}-{year}.md`
- [ ] Told user to review before converting to PPT

## Optional Data (not mandatory)

- AWS Health / PHD: only if API accessible; otherwise note limitation in Security slide
- AWS Budgets: include if configured; otherwise omit
- Cost Anomaly Detection: include spike notes in Cost Summary if significant
- Inspector: note in Security if visible; otherwise mention as visibility gap
- Service Screener: not required for monthly report

## Reference

- Customer registry: `monthly-report/report-registry.yaml`
- Registry generator: `scripts/generate_monthly_report_customers.py`
- PPT Template: `monthly-report/template/Template.pptx`
- Custom customer templates: `monthly-report/custom/<customer>/`
- Past outputs: `monthly-report/output/<slug>/<YYYY-MM>/`
- Generated `.pptx` is never committed (`.gitignore` blocks it); deliver from the working directory.
