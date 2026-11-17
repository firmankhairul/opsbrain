from __future__ import annotations
from pathlib import Path
from typing import Optional
import re

REPO_ROOT = Path(__file__).resolve().parents[2]

DOC_ALIASES = {
    "overview": "overview.md",
    "instances": "instances.md",
    "network": "network.md",
    "access": "access.md",
}


def _customer_dir(root: Path, customer: str) -> Path:
    return root / customer.lower()


def read_doc(root: Path, customer: str, doc: str) -> str:
    d = _customer_dir(root, customer)
    filename = DOC_ALIASES.get(doc.lower(), doc if doc.endswith(".md") else doc + ".md")
    path = d / "docs" / filename
    if not path.exists():
        path = d / "knowledge-base" / filename
    if not path.exists():
        return f"Doc not found: {filename} for customer {customer}"
    return path.read_text()


def list_docs(root: Path, customer: str) -> dict:
    """List a customer's documents, including per-account docs.

    Multi-account customers keep account-scoped facts in docs/<account>/
    (acme-retail has 17 such folders, acme-retail 10). Listing only the top level
    hid them entirely, so a caller asking what documentation exists got the
    customer-level files and nothing else.
    """
    d = _customer_dir(root, customer)
    result = {}
    for sub in ["docs", "knowledge-base", "tickets", "mop", "assessment",
                "incident_report", "mom", "projects", "accounts", "infra"]:
        sub_dir = d / sub
        if not sub_dir.exists():
            continue
        files = [f.name for f in sorted(sub_dir.iterdir()) if f.is_file()]
        if files:
            result[sub] = files
        # docs/<account>/ — surface each account folder under its own key,
        # addressable by read_customer_doc as "<account>/<doc>".
        if sub == "docs":
            for acc in sorted(p for p in sub_dir.iterdir() if p.is_dir()):
                acc_files = [f.name for f in sorted(acc.iterdir()) if f.is_file()]
                if acc_files:
                    result[f"docs/{acc.name}"] = acc_files
    return result


def search_kb(root: Path, customer: str, query: str) -> list[dict]:
    kb_dir = _customer_dir(root, customer) / "knowledge-base"
    if not kb_dir.exists():
        return []
    results = []
    q = query.lower()
    for f in sorted(kb_dir.iterdir()):
        if not f.is_file():
            continue
        content = f.read_text()
        if q in content.lower():
            snippet = next(
                (line.strip() for line in content.splitlines() if q in line.lower()), ""
            )
            results.append({"file": f.name, "snippet": snippet})
    return results


_STATUS_VOCAB = (
    "Pending Approval", "In Progress", "Escalated", "Resolved", "Closed", "Open", "Done",
)


def _normalise_status(raw: str) -> str:
    # Emphasis is stripped BEFORE the vocabulary match: `'** closed'` does not
    # startswith `'closed'`, so without this it fell through to the fallback and kept
    # the asterisks — and the status filter compares by equality, so the ticket then
    # matched nothing. A history row can carry bold in the cell itself
    # (`| … | **Closed** | … |`), which is where acme-retail's came from.
    raw = (raw or "").strip().strip("*").strip()
    low = raw.lower()
    for word in _STATUS_VOCAB:
        if low.startswith(word.lower()):
            return word
    return raw.split("—")[0].strip() or "Unknown"


def _read_status(content: str) -> str:
    """Read an artifact's status, tolerating every ticket shape in the repo.

    Order of preference:
      1. banner line  `> **Status:** In Progress · **Bola di:** Example MSP · …`  (current)
      2. bare line    `**Status**: In Progress`                           (legacy)
      3. the LAST dated row of the history table                          (fallback)

    The fallback exists because a handful of older tickets carry a
    `## Status History` table but no status line at all — without it they read
    "Unknown" even though their latest history row says Resolved.

    The value is normalised to a known status word so the `status=` filter can
    compare reliably. The previous regex captured `(\\w+)` only, which silently
    turned "In Progress" into "In" — filtering by "In Progress" never matched.
    """
    # `:\*{0,2}` on the second pattern: `**Status:** X` puts the colon inside the bold,
    # so stopping at the colon leaves `**` in the value — and the status filter compares
    # by equality, so the ticket then matches nothing and disappears from the listing.
    m = (re.search(r"^\s*>\s*\*\*Status:?\*\*:?\s*([^·\n]+)", content, re.MULTILINE)
         or re.search(r"^\*{0,2}Status\*{0,2}\s*:\*{0,2}\s*([^\n]+)", content,
                      re.MULTILINE))
    if m:
        return _normalise_status(m.group(1))

    rows = re.findall(r"^\|\s*20\d\d-\d\d-\d\d[^|]*\|\s*([^|]+?)\s*\|",
                      content, re.MULTILINE)
    if rows:
        return _normalise_status(rows[-1])
    return "Unknown"


def list_tickets(root: Path, customer: str, status: Optional[str] = None) -> list[dict]:
    tickets_dir = _customer_dir(root, customer) / "tickets"
    if not tickets_dir.exists():
        return []
    results = []
    for f in sorted(tickets_dir.iterdir(), reverse=True):
        if not f.is_file() or f.suffix != ".md":
            continue
        content = f.read_text()
        file_status = _read_status(content)
        if status and file_status.lower() != status.lower():
            continue
        title_m = re.search(r"^#\s+Ticket:\s+(.+)$", content, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else f.stem
        results.append({"file": f.name, "title": title, "status": file_status})
    return results


def list_open_incidents(root: Path, customer: Optional[str] = None) -> list[dict]:
    folders = (
        [_customer_dir(root, customer) / "incident_report"]
        if customer
        else [d / "incident_report" for d in root.iterdir()
              if d.is_dir() and (d / "incident_report").exists()]
    )
    results = []
    for folder in folders:
        if not folder.exists():
            continue
        cust_name = folder.parent.name
        for f in sorted(folder.iterdir(), reverse=True):
            if not f.is_file() or f.suffix != ".md":
                continue
            content = f.read_text()
            if _read_status(content).lower() == "open":
                title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                results.append({
                    "customer": cust_name,
                    "file": f.name,
                    "title": title_m.group(1).strip() if title_m else f.stem,
                })
    return results


# Every artifact directory in the workspace contract (see CLAUDE.md) that can
# hold searchable .md content. mom/ is excluded — those are .docx, not text.
ALL_SEARCH_DIRS = [
    "docs", "knowledge-base", "tickets", "mop", "incident_report",
    "assessment", "projects", "accounts",
]


def _tokenize(text: str) -> list[str]:
    # words of 2+ chars, lowercased — used for token (AND) matching so a query
    # like "RDS latency" matches a doc that says "latency" and "RDS" on
    # different lines, not only a literal "rds latency" substring.
    return re.findall(r"\w{2,}", text.lower())


def _best_snippet(lines: list[str], tokens: list[str]) -> str:
    # pick the line covering the most query tokens; ties break to the earliest.
    best, best_hits = "", 0
    for ln in lines:
        low = ln.lower()
        hits = sum(1 for t in tokens if t in low)
        if hits > best_hits:
            best, best_hits = ln.strip(), hits
            if hits == len(tokens):
                break
    return best[:200]


def search_all(root: Path, query: str, doc_type: Optional[str] = None) -> list[dict]:
    results = []
    q = query.lower().strip()
    tokens = _tokenize(q)
    search_dirs = [doc_type] if doc_type else ALL_SEARCH_DIRS
    for customer_dir in sorted(root.iterdir()):
        if not customer_dir.is_dir() or customer_dir.name.startswith("."):
            continue
        if not (customer_dir / "customer.yaml").exists():
            continue
        for sub in search_dirs:
            sub_dir = customer_dir / sub
            if not sub_dir.exists():
                continue
            # rglob, not iterdir — project folders nest (e.g.
            # projects/<name>/04-method-of-procedure/*.md).
            for f in sorted(sub_dir.rglob("*.md")):
                if not f.is_file():
                    continue
                content = f.read_text(encoding="utf-8", errors="ignore")
                low = content.lower()
                # Match when every query token appears somewhere in the doc
                # (AND semantics), order- and line-independent. Falls back to
                # the raw substring so exact-phrase queries still work.
                if tokens:
                    matched = all(t in low for t in tokens)
                else:
                    matched = q in low
                if not matched:
                    continue
                snippet = _best_snippet(content.splitlines(), tokens or [q])
                results.append({
                    "customer": customer_dir.name,
                    "section": sub,
                    "file": str(f.relative_to(customer_dir)),
                    "snippet": snippet,
                })
    return results
