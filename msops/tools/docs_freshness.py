"""How fresh are the customer docs an agent reads first? Read-only.

Docs-first only helps while the docs are true. A live check that disagrees with a doc and
never reaches it leaves the next agent with a stale picture, so the freshness of each core
doc is measured two ways:

  - age: days since it was last VERIFIED. A `Terakhir diverifikasi: YYYY-MM-DD` line in the
    file wins; without one the date of its last commit is used and the row is marked
    unstamped, because any edit moves a commit date, verified or not.
  - lag: days between that date and the latest commit anywhere in the customer folder. A
    customer worked on after its docs were last verified is the sign that live findings did
    not make it back. Lag never exceeds age, so a doc is `stale` (age over `stale_days`) or,
    if not, `behind` (lag over `behind_days`).
"""
from __future__ import annotations

import re
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from msops.tools.customers import load_customers

_ROOT = Path(__file__).resolve().parents[2]
CORE_DOCS = ("overview.md", "instances.md", "network.md", "access.md")
_STAMP = re.compile(r"Terakhir diverifikasi:\s*(\d{4}-\d{2}-\d{2})")


def read_stamp(text: str) -> Optional[date]:
    """The `Terakhir diverifikasi: YYYY-MM-DD` date in the first 40 lines, if there is one."""
    m = _STAMP.search("\n".join(text.splitlines()[:40]))
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def assess(items: list[dict], today: date, stale_days: int = 30,
           only_flagged: bool = True, limit: int = 50, behind_days: int = 14) -> dict:
    """Rate each doc. `items`: customer, path, stamp, committed, activity (dates or None)."""
    rows = []
    for it in items:
        verified = it.get("stamp") or it.get("committed")
        if verified is None:
            continue
        age = (today - verified).days
        activity = it.get("activity")
        lag = (activity - verified).days if activity else 0
        if age > stale_days:
            status = "stale"
        elif lag > behind_days:
            status = "behind"
        else:
            status = "ok"
        rows.append({
            "customer": it["customer"], "doc": it["path"], "status": status,
            "verified": verified.isoformat(),
            "source": "stamp" if it.get("stamp") else "git",
            "age_days": age, "lag_days": max(lag, 0),
        })
    flagged = [r for r in rows if r["status"] != "ok"]
    shown = flagged if only_flagged else rows
    shown.sort(key=lambda r: (-r["lag_days"], -r["age_days"], r["customer"], r["doc"]))
    return {
        "checked": len(rows),
        "flagged": len(flagged),
        "unstamped": sum(1 for r in rows if r["source"] == "git"),
        "stale_days": stale_days,
        "behind_days": behind_days,
        "docs": shown[:limit],
    }


def _git_date(repo: Path, rel: str) -> Optional[date]:
    r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%cs", "--", rel],
                       capture_output=True, text=True, timeout=30)
    s = r.stdout.strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except ValueError:
        return None


def collect(root: Path, customer: Optional[str] = None) -> list[dict]:
    """Core docs per customer with their stamp, last commit and the customer's last activity."""
    items = []
    for c in load_customers(root):
        if customer and customer.lower() not in {c.folder.lower(), c.name.lower()}:
            continue
        folder = root / c.folder
        docs_dir = folder / "docs"
        if not docs_dir.is_dir():
            continue
        # A customer kept in a git submodule is its own repository.
        repo, base = (folder, "") if (folder / ".git").exists() else (root, c.folder + "/")
        activity = _git_date(repo, base.rstrip("/") or ".")
        for name in CORE_DOCS:
            for path in sorted(docs_dir.glob(f"**/{name}")):
                rel = path.relative_to(folder).as_posix()
                items.append({
                    "customer": c.folder, "path": f"{c.folder}/{rel}",
                    "stamp": read_stamp(path.read_text(errors="ignore")),
                    "committed": _git_date(repo, base + rel),
                    "activity": activity,
                })
    return items


def doc_audit_freshness(customer: Optional[str] = None, stale_days: int = 30,
                        only_flagged: bool = True, limit: int = 50, behind_days: int = 14,
                        root: Path = _ROOT, today: Optional[date] = None) -> dict:
    return assess(collect(root, customer), today or date.today(), stale_days,
                  only_flagged, limit, behind_days)
