from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional
import json

# ensure repo root is on sys.path when server.py is run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastmcp import FastMCP

from msops.models import CustomerInfo
from msops.tools.customers import (
    load_customers, find_customer, get_all_accounts, scaffold_customer,
    create_customer_doc, CORE_DOCS, OPTIONAL_DOCS,
)
from msops.tools.docs import (
    read_doc, list_docs, search_kb,
    list_tickets, list_open_incidents, search_all
)
from msops.tools.artifacts import (
    create_project, create_project_mop,
    create_mop, create_assessment,
    create_incident_report, create_kb_entry,
    create_monthly_report, create_mom
)
from msops.tools.workflow import classify_work, update_ticket_status
from msops.tools.issue_list import list_issues as _list_issues
from msops.tools.issue_create import create_intake_issue as _create_intake_issue
from msops.tools.issue_classify import classify_issue as _classify_issue
from msops.tools.issue_resolve import assign_issue as _assign_issue, resolve_issue as _resolve_issue
from msops.tools.docs_freshness import doc_audit_freshness as _doc_audit_freshness
from msops.tools.docs_index import doc_index as _doc_index
from msops.tools.refresh_docs import refresh_customer_docs as _refresh_docs
from msops.tools.integrations import (
    sync_ticket_to_github as _sync_gh,
    get_issue as _get_issue,
    find_issue_by_title as _find_issue_by_title,
    sync_ticket_to_zoho as _sync_zoho,
    list_zoho_tickets as _list_zoho_tickets,
    get_zoho_ticket as _get_zoho_ticket,
    search_zoho_tickets as _search_zoho_tickets,
    close_zoho_ticket as _close_zoho_ticket,
    bulk_close_zoho_tickets as _bulk_close_zoho_tickets,
)
from msops.tools.tracker import (
    list_open_action_items as _list_action_items,
    check_recurrence as _check_recurrence,
)
from msops.tools.issue_audit import audit_issue_format as _audit_issue_format
from msops.tools.issue_write import update_action_item as _update_action_item
from msops.tools.issue_cleanup import (
    update_issue as _update_issue,
    split_detail_to_comment as _split_detail,
)
from msops.tools.board import set_board_fields as _set_board_fields
from msops.tools.stage import next_for as _next_for
from msops.tools.issue_analyze import analyze_issue as _analyze_issue
from msops.tools.weight_report import report_work_weight as _report_weight
from msops.tools.scope import (report_out_of_sow as _report_out_of_sow,
                               scope_candidates as _scope_candidates,
                               sow_status as _sow_status)
from msops.tools.weight_sync import sync_weight_to_board as _sync_weight

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_MOM = REPO_ROOT / "template" / "report-decks" / "mom-template.docx"

INSTRUCTIONS = """ms-ops: operations workspace for several managed-services customers.

Start with get_customer / list_customers, then read the customer's docs before touching an account. For any lookup across the repo use search_docs / search_customer_kb.
Never run a mutating action without explicit user approval: propose, wait, execute. Tools that write default to dry_run=True: show the preview, and use dry_run=False only after approval.
Create MoP, MoM, report or KB documents only when the user asks or an action item needs one. Work on a customer issue follows Get, Analyze, Ship, Done (skill ops-issue; issue_create, issue_list, issue_get). No emoji in any report, issue or ticket. Issues follow docs/standards/ops-issue-format.md; record progress with issue_update_action_item.
If the user is new or asks what is available, explain: this MCP server (customers, docs, tickets, GitHub Issues, reports, SoW scope), the 8 ops skills (entry point: ms-ops), the approval rule above, and point to docs/getting-started.md."""

mcp = FastMCP("ms-ops", instructions=INSTRUCTIONS)

# The Zoho Desk tools work only with credentials in the environment (see
# integrations._zoho_env). Without them they fail on every call and cost ~1.2k tokens of
# tool definitions in each session, so they are registered only when the credentials exist.
_ZOHO_ENV = ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN", "ZOHO_DESK_ORG_ID")
ZOHO_ENABLED = all(os.environ.get(k) for k in _ZOHO_ENV)
_zoho_tool = mcp.tool() if ZOHO_ENABLED else (lambda f: f)


def _fmt_customer(c: CustomerInfo) -> dict:
    return {
        "name": c.name,
        "display_name": c.display_name,
        "folder": c.folder,
        "providers": [
            {
                "provider": p.provider,
                "accounts": [
                    {"id": a.id, "profile": a.profile,
                     "region": a.region, "purpose": a.purpose,
                     # the IAM role names what the profile may do (ReadOnly vs admin)
                     "role": a.role}
                    for a in p.accounts
                ]
            }
            for p in c.providers
        ]
    }


@mcp.tool()
def list_customers(provider: Optional[str] = None) -> list[dict]:
    """List all customers in the repo. Optionally filter by provider (aws, huawei, azure, gcp, odoo)."""
    customers = load_customers(REPO_ROOT)
    if provider:
        customers = [c for c in customers if any(p.provider == provider for p in c.providers)]
    return [_fmt_customer(c) for c in customers]


@mcp.tool()
def get_customer(query: str) -> dict:
    """Get full customer info. Query by name, account ID, profile, or display name (fuzzy match)."""
    customers = load_customers(REPO_ROOT)
    c = find_customer(customers, query)
    if not c:
        return {"error": f"No customer found for query: {query}"}
    return _fmt_customer(c)


@mcp.tool()
def get_customer_by_account(account_id: str) -> dict:
    """Get customer by AWS/cloud account ID."""
    customers = load_customers(REPO_ROOT)
    accounts = get_all_accounts(customers)
    if account_id not in accounts:
        return {"error": f"Account ID {account_id} not found"}
    return accounts[account_id]


@mcp.tool()
def get_customer_by_ip(ip: str) -> dict:
    """Search all docs for a given IP address to identify which customer owns it."""
    results = search_all(REPO_ROOT, ip)
    if not results:
        return {"error": f"IP {ip} not found in any customer docs"}
    return {"ip": ip, "matches": results}


@mcp.tool()
def check_sso_session(profile: str) -> dict:
    """Check if an AWS SSO profile session is active or expired."""
    import subprocess
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--profile", profile],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return {"status": "active", "profile": profile, "account": data.get("Account")}
        return {
            "status": "expired",
            "profile": profile,
            "login_command": f"aws sso login --profile {profile}",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def list_all_accounts() -> dict:
    """Return flat map of all account IDs across all customers."""
    customers = load_customers(REPO_ROOT)
    return get_all_accounts(customers)


@mcp.tool()
def create_customer(name: str, folder: str, providers: list[dict]) -> dict:
    """Scaffold a new customer folder with customer.yaml and doc templates."""
    path = scaffold_customer(REPO_ROOT, name=name, folder=folder, providers=providers)
    return {"created": str(path), "files": [str(f) for f in path.rglob("*") if f.is_file()]}


@mcp.tool()
def doc_create_customer_doc(customer: str, doc: str, dry_run: bool = True) -> dict:
    """Add one customer doc from template/customer/ to <slug>/docs/ (or README.md at the root).
    Core docs (overview, instances, network, access, README) are created by create_customer;
    optional ones are added when the customer has that layer: security, kubernetes, odoo,
    cicd, monitoring, backup-dr, contacts. Never overwrites. Fill it from docs and a
    read-only live check, then set the `Terakhir diverifikasi` line. dry_run previews."""
    customers = load_customers(REPO_ROOT)
    c = find_customer(customers, customer)
    if not c:
        return {"error": f"Customer not found: {customer}", "docs": list(CORE_DOCS + OPTIONAL_DOCS)}
    try:
        r = create_customer_doc(REPO_ROOT, c.folder, doc, dry_run=dry_run)
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        return {"error": str(e), "docs": list(CORE_DOCS + OPTIONAL_DOCS)}
    if dry_run:
        path, content = r
        return {"dry_run": True, "would_create": str(path), "preview": content[:500]}
    return {"path": str(r)}


@mcp.tool()
def read_customer_doc(customer: str, doc: str) -> str:
    """Read a customer doc. doc can be: overview, instances, network, access, or any filename."""
    return read_doc(REPO_ROOT, customer, doc)


@mcp.tool()
def list_customer_docs(customer: str) -> dict:
    """List all docs, tickets, KB entries, and artifacts for a customer."""
    return list_docs(REPO_ROOT, customer)


@mcp.tool()
def search_customer_kb(customer: str, query: str) -> list[dict]:
    """Search knowledge base entries for a customer by keyword."""
    return search_kb(REPO_ROOT, customer, query)


@mcp.tool()
def list_customer_tickets(customer: str, status: Optional[str] = None) -> list[dict]:
    """List tickets for a customer. status filter: Open, Resolved, Escalated."""
    return list_tickets(REPO_ROOT, customer, status)


@mcp.tool()
def list_open_customer_incidents(customer: Optional[str] = None) -> list[dict]:
    """List all open incidents. Omit customer to search across all customers."""
    return list_open_incidents(REPO_ROOT, customer)


@mcp.tool()
def list_recent_tickets(days: int = 7, customer: Optional[str] = None) -> list[dict]:
    """List tickets from the last N days. Omit customer to search across all."""
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    folders = (
        [REPO_ROOT / customer.lower()]
        if customer
        else [d for d in REPO_ROOT.iterdir() if (d / "customer.yaml").exists()]
    )
    results = []
    for folder in folders:
        tickets_dir = folder / "tickets"
        if not tickets_dir.exists():
            continue
        for f in tickets_dir.iterdir():
            if f.is_file() and f.suffix == ".md" and f.stem[:10] >= cutoff:
                results.append({"customer": folder.name, "file": f.name})
    return sorted(results, key=lambda x: x["file"], reverse=True)


@mcp.tool()
def search_docs(query: str, doc_type: Optional[str] = None) -> list[dict]:
    """Full-text search across ALL customers and artifact types — docs, knowledge-base,
    tickets, mop, incident_report, assessment, projects (recursive), accounts. This is
    the right tool for "where is X" / "find the doc about Y" questions — it returns
    filename + one matching snippet per hit, not full file content, so it stays cheap
    even as the corpus grows. Use it before grepping or reading files by hand.
    doc_type: narrow to one directory (e.g. "tickets") instead of searching all of them."""
    return search_all(REPO_ROOT, query, doc_type)


@mcp.tool()
def doc_create_mop(customer: str, slug: str, dry_run: bool = True) -> dict:
    """Create a MoP — the single change document: approval, procedure, verification, rollback.
    Replaces the former separate Change Request. dry_run=True (default): preview only."""
    result = create_mop(REPO_ROOT, customer, slug, dry_run=dry_run)
    if dry_run:
        path, content = result
        return {"dry_run": True, "would_create": str(path), "preview": content[:600]}
    return {"path": str(result)}


@mcp.tool()
def doc_create_incident_report(customer: str, slug: str, severity: str = "P3", dry_run: bool = True) -> dict:
    """Create an Incident Report. severity: P1-P4. dry_run=True (default): preview only. dry_run=False: write file."""
    result = create_incident_report(REPO_ROOT, customer, slug, severity, dry_run=dry_run)
    if dry_run:
        path, content = result
        return {"dry_run": True, "would_create": str(path), "preview": content[:600]}
    return {"path": str(result)}


@mcp.tool()
def doc_create_project(customer: str, slug: str, dry_run: bool = True) -> dict:
    """Scaffold a project package under <slug>/projects/<slug>/: README (brief, scope,
    stakeholders, phase table), timeline.md (phases, dates, MANDAYS), tdd.md (Technical
    Design Document), tracker.md (customer-facing progress), handover.md (BAST basis +
    internal handover) and an empty mop/ for per-phase MoPs. Use for sustained,
    multi-deliverable work (migration, mass upgrade, new environment); a single change is
    an issue, not a project. Pair with one umbrella issue (issue_classify kind="project")
    and one issue per phase (**Parent**: #umbrella). Refuses a non-empty folder.
    dry_run=True previews the files."""
    try:
        result = create_project(REPO_ROOT, customer, slug, dry_run=dry_run)
    except (FileExistsError, FileNotFoundError) as e:
        return {"error": str(e)}
    if dry_run:
        d, files = result
        return {"dry_run": True, "would_create": [str(d / n) for n in files] + [str(d / "mop/")],
                "preview": {n: c[:300] for n, c in files.items()}}
    return {"path": str(result), "files": [f"{n}.md" for n in ("README", "timeline", "tdd", "tracker", "handover")],
            "next": "isi README dan timeline (mandays), tulis tdd.md, minta persetujuan TDD, lalu "
                    "doc_create_project_mop per fase"}


@mcp.tool()
def doc_create_project_mop(customer: str, project: str, phase_slug: str,
                           dry_run: bool = True) -> dict:
    """Create the full, step-by-step MoP for ONE project phase under
    <slug>/projects/<project>/mop/. Unlike a BAU MoP it never says "follow the runbook":
    prerequisites with go/no-go, communication plan, every step with exact command,
    expected result, PIC and time budget, verification, rollback per trigger, execution
    record. Set `parent:` to the runbook it is based on. dry_run=True previews."""
    try:
        result = create_project_mop(REPO_ROOT, customer, project, phase_slug, dry_run=dry_run)
    except FileNotFoundError as e:
        return {"error": str(e)}
    if dry_run:
        path, content = result
        return {"dry_run": True, "would_create": str(path), "preview": content[:600]}
    return {"path": str(result)}


@mcp.tool()
def doc_create_assessment(customer: str, slug: str, dry_run: bool = True) -> dict:
    """Create an Assessment — standalone analysis that can be handed over on its own.
    Use for cost assessments, architecture reviews, feasibility studies. Analysis that
    only justifies one change belongs in that MoP instead. dry_run=True: preview only."""
    result = create_assessment(REPO_ROOT, customer, slug, dry_run=dry_run)
    if dry_run:
        path, content = result
        return {"dry_run": True, "would_create": str(path), "preview": content[:600]}
    return {"path": str(result)}


@mcp.tool()
def doc_create_kb_entry(customer: str, slug: str, dry_run: bool = True) -> dict:
    """Create a Knowledge Base entry for a customer. dry_run=True (default): preview only."""
    result = create_kb_entry(REPO_ROOT, customer, slug, dry_run=dry_run)
    if dry_run:
        path, content = result
        return {"dry_run": True, "would_create": str(path), "preview": content[:600]}
    return {"path": str(result)}


@mcp.tool()
def doc_create_monthly_report(customer: str, period: str) -> dict:
    """Create a monthly report. period format: YYYY-MM (e.g. 2026-06)."""
    path = create_monthly_report(REPO_ROOT, customer, period)
    return {"path": str(path)}


@mcp.tool()
def doc_create_mom(customer: str, slug: str, dry_run: bool = True) -> dict:
    """Create a Minutes of Meeting document (from template if available).
    dry_run=True (default): preview only."""
    result = create_mom(REPO_ROOT, customer, slug,
                        template_path=TEMPLATE_MOM if TEMPLATE_MOM.exists() else None,
                        dry_run=dry_run)
    if dry_run:
        path, content = result
        return {"dry_run": True, "would_create": str(path), "preview": content[:600]}
    return {"path": str(result)}


@mcp.tool()
def classify_task(description: str) -> dict:
    """Classify a task description by keywords. Returns type (check / incident /
    change-low / change-high), risk, needs_issue (False only for check) and document_hint
    (whether a MoP or incident report is likely, per ops-rules rule 9). Keyword-based:
    check the result, do not trust it blindly."""
    return classify_work(description)


@mcp.tool()
def ticket_file_update_status(ticket_path: str, new_status: str, notes: str,
                  related_doc_type: Optional[str] = None,
                  related_doc_path: Optional[str] = None) -> dict:
    """LEGACY ticket-file flow. Update ticket status, refresh the banner, and append a dated row to `## Riwayat`.
    Optionally link a related document. Works on legacy tickets too (`## Status History`).
    new_status: Open, In Progress, Pending Approval, Resolved, Escalated, Closed.
    Format: docs/standards/ops-issue-format.md"""
    path = Path(ticket_path)
    if not path.exists():
        return {"error": f"Ticket not found: {ticket_path}"}
    related_doc = (related_doc_type, related_doc_path) if related_doc_type and related_doc_path else None
    update_ticket_status(path, new_status, notes, related_doc=related_doc)
    return {"updated": str(path), "new_status": new_status}


@mcp.tool()
def ticket_file_sync_to_issue(ticket_path: str, dry_run: bool = True,
                          force: bool = False) -> dict:
    """LEGACY ticket-file flow (not for issue-first work). Sync a ticket to GitHub Issues via gh CLI. Creates issue with customer label.
    dry_run=True (default): preview. dry_run=False: create issue. Requires gh CLI authenticated."""
    return _sync_gh(Path(ticket_path), dry_run=dry_run, force=force)


@_zoho_tool
def sync_ticket_to_zoho(ticket_path: str, dry_run: bool = True) -> dict:
    """Sync a local ms-ops ticket to Zoho Desk via REST API.

    Automatically maps:
    - ms-ops Status  → Zoho Desk Status (Open / In Progress / On Hold / Resolved / Closed)
    - Task type      → Zoho Type (Incident / Change Request / Service Request)
    - Task type      → Priority (High / Normal / Low)

    Subject format: "[customer] <ticket title>" — same as GitHub sync.
    Idempotent: searches for existing ticket before creating.

    dry_run=True (default): preview only, no API call.
    dry_run=False: create or update ticket in Zoho Desk.

    Required env vars (set in shell or .env):
      ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN, ZOHO_DESK_ORG_ID
    Optional:
      ZOHO_DESK_DEPT_ID  — department to file tickets under
    """
    return _sync_zoho(Path(ticket_path), dry_run=dry_run)


@_zoho_tool
def list_zoho_tickets(
    status: Optional[str] = None,
    limit: int = 25,
    dept_id: Optional[str] = None,
) -> list[dict]:
    """List tickets from Zoho Desk.

    status: Filter by status. One of: Open, In Progress, On Hold, Resolved,
            Closed, Escalated. Leave empty to see all statuses.
    limit:  Max tickets to return (1–50). Default 25.
    dept_id: Department ID to filter. Defaults to ZOHO_DESK_DEPT_ID env var.
             Leave empty to search all departments.

    Returns list of tickets sorted newest-first with: id, number, subject,
    status, priority, type, created_at, assignee, url.

    Requires env vars: ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN,
    ZOHO_DESK_ORG_ID.
    """
    return _list_zoho_tickets(status=status, limit=limit, dept_id=dept_id)


@_zoho_tool
def get_zoho_ticket(ticket_id: str) -> dict:
    """Fetch full detail of a single Zoho Desk ticket by its ID.

    Returns ticket fields + full description + list of comments/threads.
    Use list_zoho_tickets or search_zoho_tickets first to find the ticket_id.

    Requires env vars: ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN,
    ZOHO_DESK_ORG_ID.
    """
    return _get_zoho_ticket(ticket_id)


@_zoho_tool
def search_zoho_tickets(query: str, limit: int = 20) -> list[dict]:
    """Search Zoho Desk tickets by keyword.

    Searches subject and full-text content. Useful for finding tickets by
    customer name, incident keyword, or ticket title fragment.

    query: Search string (e.g. "example-b", "server down", "EXAMPLE RDS")
    limit: Max results (1–50). Default 20.

    Requires env vars: ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN,
    ZOHO_DESK_ORG_ID.
    """
    return _search_zoho_tickets(query=query, limit=limit)


@_zoho_tool
def close_zoho_ticket(ticket_id: str, reason: str = "") -> dict:
    """Close a Zoho Desk ticket by setting its status to Closed.

    ticket_id: Zoho Desk ticket ID (numeric string from list_zoho_tickets).
    reason:    Optional closing note added as a private comment before closing.

    Requires env vars: ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN,
    ZOHO_DESK_ORG_ID.
    """
    return _close_zoho_ticket(ticket_id=ticket_id, reason=reason)


@_zoho_tool
def bulk_close_zoho_tickets(
    dry_run: bool = True,
    older_than_days: Optional[int] = None,
    max_close: int = 500,
) -> dict:
    """Bulk-close Zoho Desk open tickets matching noise/auto-close patterns.

    Targets:
    - Calendar invites, OTP, system notifications — older than 7 days
    - AWS cost anomaly / alert email forwards — older than 7 days
    - DMARC / security scan reports — older than 3 days
    - AWS alerts with resolved/OK in subject — any age

    dry_run:         True (default) = preview only, nothing closed.
                     False = actually close matched tickets.
    older_than_days: Override minimum age for all patterns (days).
                     Leave empty to use per-category defaults (3 or 7 days).
    max_close:       Safety cap — stop after closing this many tickets.
                     Default 500. Increase for large bulk cleanup runs.

    Always run with dry_run=True first to review what will be closed.
    Requires env vars: ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN,
    ZOHO_DESK_ORG_ID.
    """
    return _bulk_close_zoho_tickets(
        dry_run=dry_run,
        older_than_days=older_than_days,
        max_close=max_close,
    )


@mcp.tool()
def issue_get(number: int, include_history: bool = False, comment_limit: int = 3) -> dict:
    """Read live issue body/owner/state and the latest 3 comments (2000 chars each).

    comment_count/comments_omitted and body_truncated expose missing history.
    include_history=True returns the full original comments for historical evidence;
    comment_limit=0 reads the current body without comments. No local ticket file read."""
    return _get_issue(number, include_history=include_history, comment_limit=comment_limit)


@mcp.tool()
def issue_find(title_query: str) -> list[dict]:
    """Search GitHub Issues by title, directly from GitHub via `gh` CLI (no local read)."""
    return _find_issue_by_title(title_query)


@mcp.tool()
def issue_create(customer: str, title: str, symptom: str, impact: str,
                        requester: str, environment: str = "unknown",
                        resource: str = "", evidence: str = "",
                        actions: Optional[list[str]] = None,
                        dry_run: bool = True, engagement: str = "") -> dict:
    """Create a basic issue straight on GitHub (the "Get" stage), in the 5-block body.

    customer: folder slug. engagement: the client, required for a folder that holds several
    (customer `token`, one-off requests). environment: prod | non-prod | unknown. actions: only when the
    request is already concrete; otherwise one placeholder row is written and the
    analysis replaces it. `Bobot kerja` is left TBD for whoever analyses. Refuses an
    unknown customer, a missing field, emoji and a duplicate title. Label
    `customer:<slug>`, board status Todo, no assignee. ALWAYS dry_run=True first and show
    the preview. Do not use ticket_file_sync_to_issue for this."""
    return _create_intake_issue(customer=customer, title=title, symptom=symptom,
                                impact=impact, requester=requester,
                                environment=environment, resource=resource,
                                evidence=evidence, actions=actions, dry_run=dry_run,
                                engagement=engagement)


@mcp.tool()
def doc_index(customer: str, query: str = "", include_tickets: bool = False,
              per_group: int = 8) -> dict:
    """One-page index of a customer's knowledge, built from front matter. READ-ONLY.

    Groups documents by type (docs, kb, mop, incident, assessment, project, report, runbook;
    cross-customer runbooks from kb/runbooks are always included) with title, one-line
    summary, tags, parent and verified date. Read this FIRST, then open only the file you
    need; far cheaper than searching the whole tree. Shows 8 per type and says how many more
    (`truncated`): narrow with `query` rather than raising `per_group`. `query` narrows by path, title, summary
    or tag; tickets are left out unless include_tickets. Documents without front matter still
    appear (type from the folder) and are counted in `with_front_matter`."""
    return _doc_index(customer=customer, query=query, include_tickets=include_tickets,
                      per_group=per_group)


@mcp.tool()
def doc_audit_freshness(customer: Optional[str] = None, stale_days: int = 30,
                        only_flagged: bool = True, limit: int = 50,
                        behind_days: int = 14) -> dict:
    """How fresh are the core docs (overview, instances, network, access)? READ-ONLY.

    Age = days since last verified: a `Terakhir diverifikasi: YYYY-MM-DD` line wins, else the
    last commit date (counted as unstamped). Lag = days between that and the latest commit in
    the customer folder; a customer worked on after its docs were verified means live
    findings did not make it back. Status: stale (age > stale_days), else behind
    (lag > behind_days), else ok. Run it before trusting docs-first on a customer you have not touched lately."""
    return _doc_audit_freshness(customer=customer, stale_days=stale_days,
                                only_flagged=only_flagged, limit=limit,
                                behind_days=behind_days)


@mcp.tool()
def issue_classify(number: int, type: str, env: str, priority: Optional[str] = None,
                   scope: Optional[str] = None, scope_reason: Optional[str] = None,
                   dry_run: bool = True, kind: str = "bau") -> dict:
    """Write the analysis verdict into an issue: weight, scope, board (the Analyze stage).

    type: check | kb | change-low | assessment | change-high | incident. env: prod | non-prod.
    priority: P1..P4, required for an incident. Uses the SAME weight table as the ticket
    flow, so nothing is typed by hand. For a customer whose customer.yaml names a `sow:`,
    scope ("in-sow" | "out-of-sow") is required and out-of-sow needs scope_reason (the
    clause): read scope_candidates first, the tool never decides scope from keywords.
    kind: "bau" (default) or "project" — a project is sustained multi-deliverable work
    with its own <slug>/projects/<name>/ folder: board Segment=Project, full MoPs (no
    MoP-lite), one umbrella issue per project. Changes only the `Bobot kerja` and `Scope`
    banner lines, the scope:* label and the board Weight/Segment, and posts one dated
    ACTION comment with the decision. ALWAYS dry_run=True first and show the preview."""
    return _classify_issue(number, type, env, priority=priority, scope=scope,
                           scope_reason=scope_reason, dry_run=dry_run, kind=kind)


@mcp.tool()
def issue_analyze(number: int, type: str, env: str, actions: list[str],
                  priority: Optional[str] = None, scope: Optional[str] = None,
                  scope_reason: Optional[str] = None, kind: str = "bau",
                  login: Optional[str] = None, dry_run: bool = True) -> dict:
    """Analyze in ONE call: owner, classification, action items, banner and board.

    The usual way from Get to Ship. Replaces the intake placeholder table with `actions`
    (each "Action | PIC", PIC defaults to Example MSP), writes `Bobot kerja` and `Scope` from the
    same table and checks as issue_classify, records the decision in one ACTION comment,
    sets the banner to In Progress with Tahap Ship and Next = the first item, and mirrors
    Status, Weight and Segment onto the board. `login` sets the owner when there is none.

    type, env, priority, scope, scope_reason, kind: as issue_classify. Refuses a table that
    already holds real rows (use issue_classify and issue_update_action_item there).
    ALWAYS dry_run=True first and show the preview; one approval writes everything."""
    return _analyze_issue(number, type, env, actions, priority=priority, scope=scope,
                          scope_reason=scope_reason, kind=kind, login=login, dry_run=dry_run)


@mcp.tool()
def issue_next(number: int) -> dict:
    """Where an issue stands in the flow and the ONE next step, read live from GitHub.

    Start here whenever an issue number comes up. Returns the stage (Get, Analyze, Ship,
    Done, as `Tahap`), the next step with the command to run, and who holds it. Read-only.
    The same function writes the banner's `Tahap` and `Next`, so the answer here and the
    one in the issue cannot differ."""
    return _next_for(number)


@mcp.tool()
def issue_assign(number: int, login: str, dry_run: bool = True) -> dict:
    """Give an issue an owner (GitHub login, without @). An issue may be filed and analysed
    without one, but issue_update_action_item(status="done") and issue_resolve refuse until
    it has one. Shows the current assignees first (dry_run=True), adds on dry_run=False."""
    return _assign_issue(number, login, dry_run=dry_run)


@mcp.tool()
def issue_resolve(number: int, reply_evidence: str, docs_delta: str, source: str = "",
                  force: bool = False, dry_run: bool = True) -> dict:
    """Close an issue the way the flow defines Done: fix verified, customer reply sent, Docs
    Delta recorded. Writes the `Docs Delta` row (Environment), sets the banner to Resolved,
    posts one RESOLUTION comment (reply evidence, docs delta, and `source`: who decided, e.g.
    "atas instruksi <nama>; persetujuan Pak X via WA 13 Okt"), closes the issue and sets the
    board to Done. Refuses while action items are still open (force=True overrides and says
    so) and while the issue has no owner. Every row Done does NOT do this automatically;
    this is the explicit, human-decided step. Preview in normal mode; an explicit
    end-to-end approval including closure permits dry_run=False directly (ops-rules 4–5).
    Record the actual communication recipient/channel; never invent email delivery."""
    result = _resolve_issue(number, reply_evidence, docs_delta, source=source, force=force,
                            dry_run=dry_run)
    if not dry_run and "error" not in result:
        for key in ("comment_preview", "banner_after", "docs_delta_row"):
            result.pop(key, None)
    return result


@mcp.tool()
def issue_list(customer: Optional[str] = None, assignee: Optional[str] = None,
                idle_days: Optional[int] = None, state: str = "open",
                limit: int = 50, stage: Optional[str] = None) -> dict:
    """List GitHub Issues straight from GitHub, most idle first — READ-ONLY. The daily queue.

    customer: slug (label `customer:<slug>`). assignee: a login, or "none" for issues
    nobody owns. idle_days: only issues untouched at least this long. stage: Get |
    Analyze | Ship | Done, to list one stage. Returns count (matches, up to 200, before
    limit), by_stage counts, stuck (still in Get or Analyze more than 3 days after
    filing) and rows: number, customer, title, assignees, tahap, next, stuck, age_days,
    idle_days, url. Start the day with stage="Get" and stage="Analyze": that is where
    steps get skipped. Unlike the ticket-file listings it also sees issues that have no
    ticket file."""
    return _list_issues(customer=customer, assignee=assignee, idle_days=idle_days,
                        state=state, limit=limit, stage=stage)


@mcp.tool()
def issue_audit_format(customer: str, number: Optional[int] = None,
                       only_violations: bool = True, limit: int = 0) -> dict:
    """Audit GitHub Issue bodies against docs/standards/ops-issue-format.md — READ-ONLY.

    Reports, per issue, what does not conform and the specific fix: missing blocks,
    non-standard headings with their rename/merge/move target, an unfilled weight
    placeholder, a body over the line target, and contradictions between the issue
    state, its status banner and the project board (the #316 hazard).

    Findings are ordered most-misleading first, and so are the issues, so a `limit`
    returns the ones most worth fixing. Writes nothing — use it to decide what to
    change, and to measure progress afterwards."""
    return _audit_issue_format(customer, number=number,
                               only_violations=only_violations, limit=limit)


@mcp.tool()
def issue_update_action_item(issue: int, item: int, status: str, note: str,
                       dry_run: bool = True, force: bool = False) -> dict:
    """Record progress on ONE action item of a GitHub Issue — the checkpoint mechanism.

    Use this instead of `gh issue comment` for every progress report. One call keeps in
    step the three things that must never drift apart (docs/standards/ops-issue-format.md):
      - the action-item row's state
      - the status banner, whose `Next` and `Bola di` are RECOMPUTED from the next open
        row and never typed by hand — that is what stops a body going stale
      - a dated comment holding the evidence, whose URL is linked back into the row on
        completion

    status: done | in_progress | blocked | pending | pending_approval. blocked = waiting
    on access or another team (banner Escalated); pending_approval = waiting for an
    approver (banner Pending Approval). `done` needs an owner (issue_assign). When every
    row is Done the banner stays In Progress with Next = verification, customer reply,
    Docs Delta: issue_resolve is the step that writes Resolved and closes.
    Calling `in_progress` repeatedly is
    the normal case for staged work: the row stays as-is while the banner and the comment
    trail record the movement. Repeated attempts are counted and surface the `+3 rework`
    weight adder.

    Analyze gate: `in_progress` and `done` are refused while `Bobot kerja` is still TBD;
    the refusal names the issue_classify call to run. `force=True` passes the gate and
    records that in the comment; use it only with the reason in `note`.

    Preview in normal mode. Routine checkpoints within explicit approved scope may use
    dry_run=False directly (ops-rules 4–5). Keep note to Performed / Verification / Result;
    the tool adds the action number and evidence link. No full-body archive is needed.
    Aborts rather than guessing if the action-items table cannot be parsed."""
    result = _update_action_item(issue, item, status, note, dry_run=dry_run, force=force)
    result.pop("body_after_preview", None)  # Row/banner/comment already describe the preview.
    if not dry_run and "error" not in result:
        for key in ("comment_preview", "row_before", "banner_after", "proposal"):
            result.pop(key, None)
    return result


@mcp.tool()
def issue_rewrite_body(number: int, body: Optional[str] = None, comment: Optional[str] = None,
                 reason: str = "Dirapikan ke format 5 blok "
                               "(docs/standards/ops-issue-format.md).",
                 dry_run: bool = True, force: bool = False) -> dict:
    """Rewrite ONE issue body, archiving the old one first — for legacy cleanup.

    Use this to bring an existing issue INTO the 5-block shape; use issue_update_action_item
    for an issue already in shape. You compose `body` yourself: a script cannot judge
    which prose belongs in `## Masalah` versus `## Catatan`, so the judgement stays with
    you and this tool only guarantees the cost of being wrong stays recoverable.

    Three guards, because an overwritten body cannot be recovered through the API:
      1. the old body is posted as a dated archive comment BEFORE the new one is written
      2. identifiers (instance/AMI/volume ids, IPs, cmdbid) must survive the rewrite
      3. the new body must not answer fewer of the five PM questions than the old one

    Guards 2 and 3 refuse by default; `force=True` proceeds and says so, and the archive
    comment is written either way. A changed `Bobot kerja` line is refused the same way:
    the weight is changed only through issue_classify. One issue per call — no batch mode, deliberately.
    ALWAYS run dry_run=True first and show the preview before executing."""
    return _update_issue(number, body=body, comment=comment, reason=reason,
                         dry_run=dry_run, force=force)


@mcp.tool()
def issue_move_detail_to_comment(number: int, title: str, content: str,
                            dry_run: bool = True) -> dict:
    """Move a block of detail out of an issue body into its own comment, and return the
    url to link it from — the body stays a summary, the detail stays one click away.

    Use it for raw inventories, AMI/volume lists, command output or step-by-step
    procedures that the body only carries because some action item will need them. Then
    put the returned url in that action-item row via issue_rewrite_body, so the row reads as
    the action and the link carries the detail. Do not repeat the content in the body
    afterwards — that is the duplication this avoids.

    Does not touch the body. Run with dry_run=True first."""
    return _split_detail(number, title, content, dry_run=dry_run)


@mcp.tool()
def issue_set_board_fields(customer: str, number: int, status: Optional[str] = None,
                     segment: Optional[str] = None, weight: Optional[float] = None,
                     due: Optional[str] = None, dry_run: bool = True) -> dict:
    """Set project-board fields on one issue — the board is the index a PM clicks through.

    status:  Pending Approval | Todo | In Progress | Done
    segment: Project | Monthly Report | Incident | Change | BAU
    weight:  the number from the issue's `Bobot kerja` line. The markdown is canonical;
             this is the sortable mirror, so pass the same value, do not invent one.
    due:     YYYY-MM-DD

    Only the fields you pass are touched, and every value is validated before anything
    is written — a half-applied change is worse than a refused one. A single-select is
    matched against its declared options, because `gh` accepts a wrong option id and the
    write then lands empty, which looks like it worked.

    A customer with `github_project:` in customer.yaml uses its own board; every other
    customer lands on the shared org board (#60, Customer field set automatically). Run dry_run=True
    first."""
    return _set_board_fields(customer, number, status=status, segment=segment,
                             weight=weight, due=due, dry_run=dry_run)


@mcp.tool()
def report_work_weight(customer: str, period: Optional[str] = None,
                       state: str = "closed") -> dict:
    """Total work weight for capacity planning, grouped by assignee and segment.

    period: "YYYY-MM", filtered on when the issue CLOSED — capacity is about when work
            landed. Omit for all time. state: closed (default) | open | all.

    Reports the gaps rather than printing a clean number: issues whose `Bobot kerja` is
    still an unfilled placeholder are EXCLUDED from the total and listed, because a
    placeholder silently shrinks it; issues with no assignee are counted but listed
    separately, since per-person capacity from rows that name nobody is not capacity
    planning. Co-assignees split one issue's weight rather than each claiming it.

    Read the `warnings` before quoting the total anywhere."""
    return _report_weight(customer, period=period, state=state)


@mcp.tool()
def scope_candidates(customer: str, activity: str, limit: int = 5) -> dict:
    """SoW clauses worth READING before deciding whether an activity is in scope.

    NOT a classifier and not a verdict. It ranks by shared words, deliberately dumbly,
    and returns both the in-scope and the out-of-scope candidates — reading only the
    out-of-scope list is exactly how this is decided wrongly, since that list reads as
    absolute while other clauses qualify it and the document has no precedence rule.
    Measured on the acme-retail SoW: a keyword tally over it gave 3 false positives in
    4 sampled cases, and two clauses were read backwards outright. Decide from the
    clause text; record the decision with scope= on issue_analyze or issue_classify.

    Returns gated=False for a customer with no `sow:` in customer.yaml — a normal
    answer, not an error."""
    return _scope_candidates(customer, activity, limit=limit)


@mcp.tool()
def report_out_of_sow(customer: str, period: Optional[str] = None,
                      state: str = "all") -> dict:
    """List the activities recorded as OUTSIDE a customer's Scope of Work.

    period: "YYYY-MM", filtered on when the issue CLOSED (so it excludes work still in
    flight). state: all (default) | closed | open.

    Carries no work weight: that scale is internal capacity planning, and once a number
    like `change-high x prod = 12` reaches a customer it becomes a billing unit to
    haggle over. What travels outward is the list and the count.

    Reports the gaps rather than a clean number — issues marked out-of-SoW with no
    clause named are listed under `action_needed`, since without the clause the list is
    not usable as evidence, and issues with no Scope line at all are counted separately
    because they predate the rule."""
    return _report_out_of_sow(customer, period=period, state=state)


@mcp.tool()
def sow_status(customer: str) -> dict:
    """Whether a customer is gated on Scope of Work classification, and why not if it is
    not. The switch is the `sow:` field in customer.yaml, never the presence of a SoW
    file in the folder — three customers have SoW documents sitting in the repo and one
    of them has four, so "which SoW" is a real question that filename detection would
    answer by guessing. Reports a `sow:` pointing at a missing file instead of letting
    the gate sit silently inert."""
    return _sow_status(customer)


@mcp.tool()
def sync_weight_to_board(customer: str, dry_run: bool = True) -> dict:
    """Mirror each issue's `Bobot kerja` onto its project-board Weight field.

    The markdown is canonical and the board is the sortable mirror — but GitHub Projects
    Insights reads the BOARD, so a weight that exists only in the body is invisible to
    every chart built there. On acme-retail that gap was 11 issues worth 98, enough to
    make a capacity chart report 230 where the real figure was 328.

    One direction only: markdown -> board, never back. Only the Weight field is touched.
    Issues with no numeric weight are skipped, which correctly includes umbrellas. An
    issue absent from the board is reported, not added — adding silently across a whole
    customer would reshape someone's board. A board value that disagrees is overwritten
    and reported, because markdown wins.

    Run dry_run=True first and show the plan."""
    return _sync_weight(customer, dry_run=dry_run)


@mcp.tool()
def refresh_customer_docs(customer: str, doc_type: str = "all", profile: Optional[str] = None,
                          dry_run: bool = True) -> dict:
    """Regenerate instances.md / network.md from AWS live state (EC2, RDS, VPC, subnets).
    doc_type: all | instances | network. dry_run (default) returns a unified diff per doc
    against what the doc says now, without writing: read it, then run dry_run=False.
    profile: required when the customer has more than one AWS account; the tool never
    picks one for you. Needs an active SSO session for that profile. After writing, set
    the doc's `Terakhir diverifikasi` line (Docs Delta)."""
    customers = load_customers(REPO_ROOT)
    c = find_customer(customers, customer)
    if not c:
        return {"error": f"Customer not found: {customer}"}
    aws_provider = next((p for p in c.providers if p.provider == "aws"), None)
    accounts = [a for a in (aws_provider.accounts if aws_provider else []) if a.profile]
    if not accounts:
        return {"error": f"No AWS accounts with a CLI profile for {c.name}"}
    if profile:
        acc = next((a for a in accounts if a.profile == profile), None)
        if acc is None:
            return {"error": f"profile {profile!r} tidak ada di {c.folder}/customer.yaml",
                    "profiles": [a.profile for a in accounts]}
    elif len(accounts) == 1:
        acc = accounts[0]
    else:
        return {"error": f"{c.name} punya {len(accounts)} akun AWS; sebutkan profile=",
                "accounts": [{"profile": a.profile, "id": a.id, "purpose": a.purpose,
                              "role": a.role} for a in accounts]}
    return _refresh_docs(REPO_ROOT, c.folder, acc.profile, acc.region, doc_type, dry_run=dry_run)


@mcp.tool()
def list_open_action_items(customer: Optional[str] = None) -> list[dict]:
    """List every unchecked `- [ ]` action item across tickets and MoPs.
    Scans one customer if given, else all. Sorted oldest-first then by priority —
    surfaces follow-ups that were never closed (the cause of recurring incidents)."""
    return _list_action_items(REPO_ROOT, customer)


@mcp.tool()
def check_recurrence(customer: str, needle: str) -> dict:
    """Recurrence guard: find prior history for a customer mentioning `needle` (server id,
    resource, tag, keyword). Run before opening an issue or writing a MoP. Searches the
    customer's files (tickets, MoP, incident reports, KB), its GitHub Issues (`issues`) and
    cross-customer runbooks in kb/runbooks (`runbooks`, candidate MoP parents).
    `any_history` is true if any of them matched."""
    return _check_recurrence(REPO_ROOT, customer, needle, include_issues=True)


if __name__ == "__main__":
    mcp.run()
