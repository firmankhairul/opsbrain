"""Action-item tracker + recurrence guard.

Task tracking lives in the artifact files themselves: open action items are
unchecked `- [ ]` checkboxes inside tickets and MoPs. These helpers surface
them (so nothing rots unclosed, the way the acme-retail 8 Jul items did until
the 23 Jul recurrence) and let a workflow check whether a target has prior
incidents before a new ticket is opened.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Optional
import re

from msops.tools.action_status import is_done

_UNCHECKED = re.compile(r"^\s*[-*]\s+\[ \]\s+(.*\S)\s*$")
# Current ticket shape keeps action items in a table instead of checkboxes, so the
# PIC can be named per row (see docs/standards/ops-issue-format.md):
#   | 1 | Cek secure channel | Example MSP | Pending |
# Anything whose Status cell is not Done is still open — that covers Pending,
# In Progress and Blocker (and their legacy emoji forms) without enumerating them.
_TABLE_ROW = re.compile(
    r"^\|\s*\d+\s*\|(?P<action>[^|]*)\|(?P<pic>[^|]*)\|(?P<status>[^|]*)\|\s*$"
)


def _open_items_in_line(line: str) -> Optional[tuple[str, Optional[str]]]:
    """Return (text, pic) when the line is an OPEN action item, else None.

    Recognises both the legacy `- [ ]` checkbox and the current action-items
    table row. Rows with an empty Action cell are skipped — the scaffolded
    template ships one such placeholder row, and listing it as an open item
    would be noise in every new ticket.
    """
    m = _UNCHECKED.match(line)
    if m:
        return m.group(1), None

    m = _TABLE_ROW.match(line)
    if m:
        action = m.group("action").strip()
        status = m.group("status").strip()
        if action and not is_done(status):
            return action, (m.group("pic").strip() or None)
    return None
_PRIORITY = re.compile(r"\bP([1-4])\b")
_DATE = re.compile(r"\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})")


def _customer_dir(root: Path, customer: str) -> Path:
    return root / customer.lower()


def _iter_customers(root: Path):
    for d in sorted(root.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and (d / "customer.yaml").exists():
            yield d


def _file_date(content: str, path: Path) -> Optional[str]:
    m = _DATE.search(content)
    if m:
        return m.group(1)
    # Fall back to a YYYY-MM-DD embedded in the filename (ticket/incident convention).
    fm = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    return fm.group(1) if fm else None


def _age_days(datestr: Optional[str]) -> Optional[int]:
    if not datestr:
        return None
    try:
        y, m, d = map(int, datestr.split("-"))
        return (date.today() - date(y, m, d)).days
    except ValueError:
        return None


def _scan_dir(cust_dir: Path, sub: str) -> list[dict]:
    d = cust_dir / sub
    if not d.exists():
        return []
    items = []
    for f in sorted(d.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue
        content = f.read_text()
        datestr = _file_date(content, f)
        age = _age_days(datestr)
        for line in content.splitlines():
            found = _open_items_in_line(line)
            if not found:
                continue
            text, pic = found
            pr = _PRIORITY.search(text)
            items.append({
                "customer": cust_dir.name,
                "source": sub,
                "file": f.name,
                "path": str(f.relative_to(cust_dir.parent)),
                "item": text,
                "pic": pic,
                "priority": f"P{pr.group(1)}" if pr else None,
                "date": datestr,
                "age_days": age,
            })
    return items


def list_open_action_items(root: Path, customer: Optional[str] = None) -> list[dict]:
    """Return every unchecked `- [ ]` action item across tickets and MoPs.

    Scans one customer when given, otherwise all registered customers. Sorted
    oldest-first (an item unclosed for 40 days should outrank a fresh one), then
    by priority.
    """
    dirs = [_customer_dir(root, customer)] if customer else list(_iter_customers(root))
    out: list[dict] = []
    for cd in dirs:
        if not cd.exists():
            continue
        out.extend(_scan_dir(cd, "tickets"))
        out.extend(_scan_dir(cd, "mop"))
    # Oldest first (None ages sink to the bottom); tie-break by priority rank.
    def _rank(it):
        pr = int(it["priority"][1]) if it["priority"] else 9
        age = it["age_days"] if it["age_days"] is not None else -1
        return (-age, pr)
    out.sort(key=_rank)
    return out


def _search_issues(customer: str, needle: str, limit: int = 20) -> dict:
    """Issues of this customer whose title or body mentions `needle`, straight from GitHub.

    Work that starts as an issue has no ticket file, so the file search alone cannot see it.
    A failure (no network, no gh) is reported, never raised: the recurrence guard must not
    break the workflow it guards."""
    import json
    from msops.tools.integrations import REPO, _run
    r = _run(["gh", "issue", "list", "--repo", REPO, "--state", "all",
              "--label", f"customer:{customer.lower()}", "--search", needle,
              "--json", "number,title,state,url", "--limit", str(limit)])
    if r.returncode != 0:
        return {"issues": [], "issues_error": r.stderr.strip()[:200]}
    try:
        return {"issues": json.loads(r.stdout or "[]")}
    except json.JSONDecodeError:
        return {"issues": [], "issues_error": "unparseable gh output"}


def _search_runbooks(root: Path, needle: str) -> list[dict]:
    """Cross-customer runbooks (`kb/runbooks/`) that mention `needle`: candidate MoP parents."""
    d = root / "kb" / "runbooks"
    q = needle.lower()
    out = []
    if d.is_dir():
        for f in sorted(d.rglob("*.md")):
            text = f.read_text(encoding="utf-8", errors="ignore")
            if q in text.lower() or q in f.name.lower():
                out.append({"path": str(f.relative_to(root)),
                            "title": next((ln.lstrip("# ").strip() for ln in text.splitlines()
                                           if ln.startswith("# ")), f.name)})
    return out


def check_recurrence(root: Path, customer: str, needle: str,
                     include_issues: bool = False) -> dict:
    """Find prior artifacts for a customer mentioning `needle` (server id, tag,
    resource, keyword) — the recurrence guard to run before opening a new ticket
    or writing a new MoP.

    Searches tickets, mop, incident_report, and knowledge-base (recursively, so
    nested project MoPs are found too). Returns matches with a snippet plus a
    count so a workflow can warn 'this target already has history' — and, for
    mop matches, point at the existing document instead of drafting a new one.

    Also returns `issues` (this customer's GitHub Issues mentioning the needle) and
    `runbooks` (`kb/runbooks/`, candidate MoP parents). `recurrence`, `count` and `matches`
    keep describing the files only; `any_history` is true if any of the three found something.
    The GitHub search is opt-in (`include_issues=True`, which the MCP tool sets) so that library
    callers and tests stay offline.
    """
    cust_dir = _customer_dir(root, customer)
    q = needle.lower()
    matches: list[dict] = []
    for sub in ("tickets", "mop", "incident_report", "knowledge-base"):
        d = cust_dir / sub
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.md"), reverse=True):
            if not f.is_file():
                continue
            content = f.read_text(encoding="utf-8", errors="ignore")
            if q not in content.lower():
                continue
            snippet = next(
                (ln.strip() for ln in content.splitlines() if q in ln.lower()), ""
            )
            matches.append({
                "section": sub,
                "file": f.name,
                "path": str(f.relative_to(cust_dir.parent)),
                "snippet": snippet[:200],
            })
    found = _search_issues(customer, needle) if include_issues else {"issues": []}
    runbooks = _search_runbooks(root, needle)
    return {
        "customer": customer,
        "needle": needle,
        "count": len(matches),
        "recurrence": len(matches) > 0,
        "matches": matches,
        "issues": found["issues"],
        **({"issues_error": found["issues_error"]} if "issues_error" in found else {}),
        "runbooks": runbooks,
        "any_history": bool(matches or found["issues"] or runbooks),
    }
