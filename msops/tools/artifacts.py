from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
import shutil

from msops.tools.customers import load_customers, find_customer

# Templates are repo assets, resolved relative to this package — not the
# customer-data `root` passed into the create_* functions.
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "template" / "artifacts"


def _today() -> str:
    return date.today().isoformat()


def _customer_dir(root: Path, customer: str) -> Path:
    """Resolve a customer query to its folder via the registry — same fuzzy
    match as get_customer (exact name, account ID, profile, display name,
    folder). Falls back to a literal lowercase slug only when the registry
    has no match, e.g. scaffolding a brand-new customer before customer.yaml
    exists."""
    match = find_customer(load_customers(root), customer)
    folder = match.folder if match else customer.lower()
    return root / folder


def _render_template(root: Path, name: str, **ctx) -> str:
    """Render template/artifacts/<name>.md with {placeholder} substitution.

    Prefer a template under the passed `root` (per-repo override); fall back to
    the templates shipped with this package when `root` has none.
    """
    tpl = root / "template" / "artifacts" / f"{name}.md"
    if not tpl.exists():
        tpl = TEMPLATE_DIR / f"{name}.md"
    return tpl.read_text(encoding="utf-8").format(**ctx)


def _artifact_ctx(customer: str, slug: str, **extra) -> dict:
    ctx = {
        "customer": customer.upper(),
        "customer_raw": customer,
        "date": _today(),
        "slug": slug,
        "title": slug.replace("-", " ").title(),
    }
    ctx.update(extra)
    return ctx


def _ticket_body(task_type: str) -> str:
    """Return block 5 of the 6-block ticket shape — the only block that differs
    per task type.

    Blocks 1–4 (banner, Environment, Masalah, Action items) are identical for every
    type and live in create_ticket. There is no block 6 — `## Referensi` was dropped
    on 2026-09-30. Block 5 carries what is
    NOT a task: incidents title it "Root cause" because that is what people look
    for by name; changes title it "Catatan & keputusan".

    Shape defined in docs/standards/ops-issue-format.md.
    """
    if task_type == "incident":
        return (
            "## Root cause\n\n"
            "<!-- Versi TERKINI saja. Kalau temuan berubah, tulis eksplisit:\n"
            '     "sebelumnya diduga X → dikoreksi jadi Y (lihat comment)".\n'
            "     HANYA hal yang mencegah aksi salah; riwayat ke comment. -->\n\n\n"
        )
    elif task_type in ("change-low", "change-high"):
        return (
            "## Catatan & keputusan\n\n"
            "<!-- HANYA hal yang mencegah orang melakukan aksi salah: keputusan yang\n"
            "     sudah dikoreksi, blocker aktif + alasannya, peringatan untuk masa\n"
            '     depan (mis. "AMI rollback jangan dihapus"). Riwayat ke comment. -->\n\n\n'
        )
    else:
        # check or unknown — minimal body
        return "## Catatan\n\n\n"


# Base weights from docs/standards/ops-issue-format.md. Incident is keyed by severity
# because that is what sets it — P1 is four times P4.
_BASE_WEIGHT = {
    "check": 1, "kb": 2, "change-low": 3, "assessment": 5, "change-high": 8,
    "incident-P4": 3, "incident-P3": 5, "incident-P2": 8, "incident-P1": 13,
}


SEVERITY_PLACEHOLDER = "<P1..P4>"


def _scope_line_if_gated(root: Path, customer: str, scope: str | None,
                         reason: str | None) -> str:
    """The `Scope` line, or nothing at all when the customer has no SoW.

    Gated per customer so acme-retail can go first without touching the other 46:
    the switch is the `sow:` field in customer.yaml, not the presence of a SoW file.
    """
    from msops.tools.scope import has_sow, scope_line
    if not has_sow(customer, root):
        return ""
    return scope_line(scope, reason)


def _weight_line(task_type: str, env: str | None,
                 priority: str | None = None) -> str:
    """The `Bobot kerja` banner line, computed when it can be and left as a placeholder
    when it cannot.

    Filling only the base weight would be WORSE than the placeholder: the aggregation
    regex matches a digit, so an unmultiplied 8 on a production change silently reports
    12 as 8 — a 33% undercount with nothing flagging it. The placeholder parses as
    nothing and `issue_audit_format` reports it, which is the honest failure.

    `env` is not inferred from the slug: measured across 188 ticket files, naming gives
    no answer for 78% of them, so inference would default silently on four tickets out
    of five. `priority` is not inferred either — severity is a judgement about business
    impact, not a word match: "down" fits a dev box (P4) and the main ERP (P1) equally.

    An incident without `priority` therefore keeps the placeholder, and the creation
    gate in ticket_file_sync_to_issue refuses the issue until it is filled. That is on
    purpose: before this, start_workflow created every incident report as P3 by default,
    silently, and the weight was never recorded at all.
    """
    key = task_type
    if task_type == "incident":
        if priority not in ("P1", "P2", "P3", "P4"):
            return "> **Bobot kerja:** <n> — <insiden P1=13 · P2=8 · P3=5 · P4=3> × <produksi 1,5 / non-produksi 1>\n"
        key = f"incident-{priority}"
    base = _BASE_WEIGHT.get(key)
    if base is None or env not in ("prod", "non-prod"):
        return "> **Bobot kerja:** <n> — <jenis> × <produksi 1,5 / non-produksi 1>\n"
    # Half UP, not Python's banker's rounding. The standard's own worked example #27
    # is `change-low 3 × 1,5 + 3 analysis = 8`, i.e. 4.5 rounded to 5 — round(4.5)
    # returns 4 and would have produced 7.
    total = int(base * (1.5 if env == "prod" else 1) + 0.5)
    mult = "produksi (1,5)" if env == "prod" else "non-produksi (1)"
    label = f"insiden {priority}" if task_type == "incident" else f"dasar {base}"
    suffix = f" ({base})" if task_type == "incident" else ""
    return f"> **Bobot kerja:** {total} — {label}{suffix} × {mult}\n"


def create_ticket(root: Path, customer: str, slug: str, dry_run: bool = False,
                  task_type: str = "change-low", env: str | None = None,
                  priority: str | None = None, scope: str | None = None,
                  scope_reason: str | None = None):
    """Scaffold a ticket in the 5-block shape (docs/standards/ops-issue-format.md).

    The ticket file and the issue body deliberately DIVERGE (decided 2026-09-30).
    The ticket is the working document and keeps `## Riwayat`, because
    update_ticket_status appends there and that is what keeps its banner fresh. The
    issue body must not have it — it duplicates the banner. So
    ticket_file_sync_to_issue derives a body on create and never overwrites one
    afterwards; see `derive_issue_body`.

    The banner's first two lines are rewritten by update_ticket_status, which is what
    keeps a ticket from going stale — the old template only ever appended history and
    never touched the header, so a closed ticket could still read "Status: Open".

    There is no `## Referensi`: it was dropped because nothing maintained it, so it
    rotted first. Documents go in the `Dokumen` row of `## Environment` (filled by
    `related_doc`), and evidence rides on the action-item row it documents.

    History lives in a "## Riwayat" table at the bottom, not in the middle of the
    document, so the blocks a reader needs first stay on the first screen.

    `env` ("prod" / "non-prod") lets the weight be computed instead of left as `<n>`;
    an incident additionally needs `priority` ("P1".."P4"), because P1 is four times P4.
    Pass it when the caller knows — an agent that just resolved the customer and the
    server does. It is deliberately NOT inferred from the slug: naming answers for only
    22% of existing tickets.

    `scope` ("in-sow" / "out-of-sow") and `scope_reason` add the `Scope` banner line,
    and ONLY for a customer whose customer.yaml names a `sow:`. A customer with no SoW
    in the repo gets no line at all rather than a placeholder nobody can resolve —
    there would be no document to resolve it against. Like `env` and `priority`, it is
    never inferred; see msops/tools/scope.py for why a matcher over a SoW is worse than
    an empty field.
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M")
    ticket_id = f"TKT-{date_str}-{slug}"
    d = _customer_dir(root, customer) / "tickets"
    path = d / f"{date_str}-{slug}.md"
    content = (
        f"# Ticket: {slug.replace('-', ' ').title()}\n\n"
        # Block 1 — status banner. Kept to three lines so "where does this stand"
        # is answerable without scrolling.
        f"> **Status:** Open · **Bola di:** Example MSP · **Next:** <langkah berikutnya>\n"
        f"> **Update terakhir:** {time_str} — ticket dibuat\n"
        # The weight table is deliberately NOT inlined here. _extract_task_type in
        # integrations.py infers the Zoho task type by keyword-scanning the whole
        # ticket, so spelling out "change-high"/"incident" in the scaffold would
        # mislabel every new ticket. Point at the standard instead.
        f"{_weight_line(task_type, env, priority)}"
        f"{_scope_line_if_gated(root, customer, scope, scope_reason)}"
        f"<!-- Tabel bobot & format: docs/standards/ops-issue-format.md -->\n\n"
        f"**ID**: {ticket_id} · **Customer**: {customer.upper()} · **Requester**: \n\n"
        # Block 2 — identifiers. These are what make an old ticket findable later,
        # so they stay in the body even when long.
        f"## Environment\n\n"
        f"| Item | Value |\n"
        f"|---|---|\n"
        f"| Instance | |\n"
        f"| cmdbid / IP | |\n"
        f"| OS / Type | |\n"
        f"| Account / Region | |\n"
        f"| Dokumen | |\n\n"
        # Block 3
        f"## Masalah\n\n\n"
        # Block 4 — progress map. PIC is one of Example MSP / Tim App / PIC Customer.
        # Status is plain text, no emoji: Done (+tanggal) · In Progress · Pending · Blocker.
        f"## Action items\n\n"
        f"| # | Action | PIC | Status |\n"
        f"|---|--------|-----|--------|\n"
        f"| 1 | | Example MSP | Pending |\n\n"
        # Block 5 — per task type. There is no block 6: `## Referensi` was dropped on
        # 2026-09-30 because nothing maintained it, so it was the first thing to rot.
        # Evidence now rides on the action-item row it documents (written there by
        # issue_update_action_item from the comment it just posted), and standing documents
        # live in the `Dokumen` row of ## Environment above.
        f"{_ticket_body(task_type)}"
        # Dated trail, appended by update_ticket_status. Last section by design.
        f"## Riwayat\n\n"
        f"| Timestamp | Status | Notes |\n"
        f"|-----------|--------|-------|\n"
        f"| {time_str} | Open | Ticket dibuat |\n"
    )
    if dry_run:
        return path, content
    d.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_mop(root: Path, customer: str, slug: str, dry_run: bool = False) -> Path:
    d = _customer_dir(root, customer) / "mop"
    path = d / f"MoP-{_today()}-{slug}.md"
    content = _render_template(root, "mop", **_artifact_ctx(customer, slug))
    if dry_run:
        return path, content
    d.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_incident_report(root: Path, customer: str, slug: str,
                           severity: str | None = None, dry_run: bool = False) -> Path:
    """`severity` is never defaulted.

    P1 is worth four times P4 and it sets the response clock, so a report born "P3"
    because nobody said otherwise carries a number no one decided. Absent or outside
    P1..P4 it stays a placeholder, which reads as unfilled and parses as nothing --
    the same honest failure `_weight_line` makes for the same reason.
    """
    d = _customer_dir(root, customer) / "incident_report"
    path = d / f"incident-{_today()}-{slug}.md"
    sev = severity if severity in ("P1", "P2", "P3", "P4") else SEVERITY_PLACEHOLDER
    content = _render_template(root, "incident_report", **_artifact_ctx(customer, slug, severity=sev))
    if dry_run:
        return path, content
    d.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_kb_entry(root: Path, customer: str, slug: str, dry_run: bool = False) -> Path:
    d = _customer_dir(root, customer) / "knowledge-base"
    path = d / f"KB-{_today()}-{slug}.md"
    content = _render_template(root, "kb", **_artifact_ctx(customer, slug))
    if dry_run:
        return path, content
    d.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_assessment(root: Path, customer: str, slug: str, dry_run: bool = False) -> Path:
    d = _customer_dir(root, customer) / "assessment"
    path = d / f"ASMT-{_today()}-{slug}.md"
    content = _render_template(root, "assessment", **_artifact_ctx(customer, slug))
    if dry_run:
        return path, content
    d.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


PROJECT_FILES = ("README", "timeline", "tdd", "tracker", "handover")


def create_project(root: Path, customer: str, slug: str, dry_run: bool = False):
    """Scaffold <slug>/projects/<name>/: brief, timeline (mandays), TDD, tracker, handover and
    an empty mop/ for the per-phase MoPs. Returns (dir, {file: content}) on dry_run, else dir.

    A project is not a bigger issue: it is paced in phases, each with its own issue, mandays
    and a full MoP, and it ends with a handover the customer signs (BAST). The package exists
    so none of those is improvised per project."""
    d = _customer_dir(root, customer) / "projects" / slug
    ctx = _artifact_ctx(customer, slug)
    files = {f"{name}.md": _render_template(root, f"project/{name}", **ctx) for name in PROJECT_FILES}
    if dry_run:
        return d, files
    if d.exists() and any(d.iterdir()):
        raise FileExistsError(f"{d} sudah ada dan tidak kosong — isi yang ada tidak ditimpa")
    (d / "mop").mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (d / name).write_text(content)
    return d


def create_project_mop(root: Path, customer: str, project: str, phase_slug: str,
                       dry_run: bool = False):
    """A full, step-by-step MoP for one project phase, under projects/<project>/mop/."""
    pdir = _customer_dir(root, customer) / "projects" / project
    if not pdir.is_dir():
        raise FileNotFoundError(f"{pdir} tidak ada — doc_create_project dulu")
    path = pdir / "mop" / f"MoP-{_today()}-{phase_slug}.md"
    content = _render_template(root, "project/mop-phase", **_artifact_ctx(customer, project),
                               ).replace("# MoP: ", f"# MoP: {phase_slug.replace('-', ' ').title()} — ", 1)
    if dry_run:
        return path, content
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_monthly_report(root: Path, customer: str, period: str, dry_run: bool = False) -> Path:
    d = _customer_dir(root, customer) / "monthly-report"
    month_label = period  # YYYY-MM
    path = d / f"monthly-report-{period}.md"
    todo = "> **TODO**\n"
    content = (
        f"# Monthly Report — {customer.upper()} | {month_label}\n\n"
        f"**Period:** {period}-01 – {period}-30\n"
        f"**Account(s):** \n"
        f"**Generated:** {_today()}\n\n"
        f"---\n\n"
        f"## Executive Summary\n\n"
        f"{todo}\n"
        f"### Approval Status\n\n"
        f"- Approved: \n"
        f"- Pending: \n\n"
        f"### Top Recommendations\n\n"
        f"1. \n"
        f"2. \n"
        f"3. \n\n"
        f"---\n\n"
        f"## Service Portfolio\n\n"
        f"{todo}\n"
        f"---\n\n"
        f"## Cost Summary\n\n"
        f"{todo}\n"
        f"**Total:** USD — | **vs Last Month:** — | **Daily Avg:** USD — | **Peak Day:** USD — (—)\n\n"
        f"### Top 10 Services by Cost\n\n"
        f"| # | Service | This Month (USD) | Prev Month (USD) | Delta | % Change |\n"
        f"|---|---------|-----------------|-----------------|-------|----------|\n"
        f"| 1 | | | | | |\n\n"
        f"### EC2 Instance Breakdown\n\n"
        f"| Instance Name | Type | Cost (USD) |\n"
        f"|---------------|------|------------|\n"
        f"| | | |\n\n"
        f"### EC2 Other\n\n"
        f"| Category | Cost (USD) |\n"
        f"|----------|------------|\n"
        f"| EBS Volumes | |\n"
        f"| EBS Snapshots | |\n"
        f"| Data Transfer | |\n\n"
        f"---\n\n"
        f"## Usage & Utilization\n\n"
        f"{todo}\n"
        f"### Compute — EC2\n\n"
        f"| Instance | Type | CPU Avg | CPU Max | Finding | Recommendation |\n"
        f"|----------|------|---------|---------|---------|----------------|\n"
        f"| | | | | | |\n\n"
        f"---\n\n"
        f"## Security & Operational Posture\n\n"
        f"{todo}\n"
        f"---\n\n"
        f"## WAFR Observations\n\n"
        f"{todo}\n"
        f"| Pillar | Status | Observation | Priority |\n"
        f"|--------|--------|-------------|----------|\n"
        f"| Operational Excellence | Green | | |\n"
        f"| Security | Green | | |\n"
        f"| Reliability | Green | | |\n"
        f"| Performance Efficiency | Green | | |\n"
        f"| Cost Optimization | Green | | |\n"
        f"| Sustainability | Green | | |\n\n"
        f"*Based on monthly operational telemetry. Not a formal AWS Well-Architected Review.*\n\n"
        f"---\n\n"
        f"## Recommendations\n\n"
        f"{todo}\n"
        f"| # | Recommendation | Priority | Est. Impact | Approval |\n"
        f"|---|---------------|----------|-------------|----------|\n"
        f"| 1 | | HIGH | Save ~USD /mo | Pending |\n\n"
        f"---\n\n"
        f"## Cost Optimization Opportunities\n\n"
        f"{todo}\n"
        f"| Resource | Current State | Recommended Action | Est. Savings (USD/mo) |\n"
        f"|----------|---------------|--------------------|-----------------------|\n"
        f"| | | | |\n\n"
        f"---\n\n"
        f"## Tickets This Period\n\n"
        f"{todo}\n"
        f"| Ticket ID | Title | Status | Resolution Summary |\n"
        f"|-----------|-------|--------|-------------------|\n"
        f"| | | | |\n\n"
        f"---\n\n"
        f"## Pending Validation\n\n"
        f"{todo}\n"
    )
    if dry_run:
        return path, content
    d.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_mom(root: Path, customer: str, slug: str, template_path: Path = None, dry_run: bool = False) -> Path:
    d = _customer_dir(root, customer) / "mom"
    path = d / f"MoM-{_today()}-{slug}.docx"

    if dry_run:
        content = _render_template(root, "mom", **_artifact_ctx(customer, slug))
        return path, content

    d.mkdir(parents=True, exist_ok=True)
    if template_path and template_path.exists():
        shutil.copy(template_path, path)
    else:
        from docx import Document
        doc = Document()
        doc.add_heading(f"Minutes of Meeting — {slug.replace('-', ' ').title()}", 0)
        doc.add_paragraph(f"Date: {_today()}")
        doc.add_paragraph("Customer: " + customer.upper())
        doc.add_heading("Attendees", 1)
        doc.add_heading("Agenda", 1)
        doc.add_heading("Discussion Points", 1)
        doc.add_heading("Action Items", 1)
        doc.add_heading("Next Meeting", 1)
        doc.save(str(path))
    return path
