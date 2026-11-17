"""List GitHub Issues by owner and idleness — the read half of Get (assign) and of the stale sweep.

Reads straight from GitHub. The ticket-file listings (`list_customer_tickets`,
`list_open_action_items`) cannot see an issue that has no ticket file, which is
most of the open backlog. Writes nothing.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from msops.tools.integrations import REPO, _run

_FIELDS = "number,title,state,body,assignees,labels,createdAt,updatedAt,url"
_FETCH_CAP = 200


def build_command(customer: Optional[str], assignee: Optional[str], state: str,
                  fetch_limit: int) -> list[str]:
    """The `gh` command for the filters. `assignee="none"` means unassigned."""
    cmd = ["gh", "issue", "list", "--repo", REPO, "--state", state,
           "--json", _FIELDS, "--limit", str(fetch_limit)]
    if customer:
        cmd += ["--label", f"customer:{customer}"]
    search = "sort:updated-asc"
    if assignee == "none":
        search = "no:assignee " + search
    elif assignee:
        cmd += ["--assignee", assignee]
    return cmd + ["--search", search]


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# An issue still in Get or Analyze this many days after it was filed has stalled at the
# step that is easiest to skip; it is flagged so the daily list starts there.
STUCK_DAYS = 3


def shape_issues(rows: list[dict], now: datetime, idle_days: Optional[int] = None,
                 limit: int = 50, stage: Optional[str] = None) -> dict:
    """Compact rows, most idle first. `count` is the match total before `limit` cuts
    (itself capped at the 200 issues fetched). Each row carries its Tahap and Next, the
    same answer `issue_next` gives, and `by_stage` counts the whole match."""
    from msops.tools.stage import stage_of
    out = []
    by_stage: dict[str, int] = {}
    for r in rows:
        idle = (now - _parse(r["updatedAt"])).days
        if idle_days is not None and idle < idle_days:
            continue
        st = stage_of(r.get("body") or "", r.get("assignees") or [], r.get("state") or "OPEN",
                      r["number"])
        if stage and st.name.lower() != stage.lower():
            continue
        by_stage[st.name] = by_stage.get(st.name, 0) + 1
        age = (now - _parse(r["createdAt"])).days
        customer = next((l["name"].split(":", 1)[1] for l in r.get("labels", [])
                         if l["name"].startswith("customer:")), "")
        out.append({
            "number": r["number"],
            "customer": customer,
            "title": r["title"],
            "assignees": [a["login"] for a in r.get("assignees", [])],
            "tahap": st.label,
            "next": st.next,
            "stuck": st.name in ("Get", "Analyze") and age > STUCK_DAYS,
            "age_days": age,
            "idle_days": idle,
            "url": r["url"],
        })
    out.sort(key=lambda x: (-x["idle_days"], x["number"]))
    return {"count": len(out), "by_stage": by_stage,
            "stuck": sum(1 for i in out if i["stuck"]), "issues": out[:limit]}


def list_issues(customer: Optional[str] = None, assignee: Optional[str] = None,
                idle_days: Optional[int] = None, state: str = "open",
                limit: int = 50, stage: Optional[str] = None) -> dict:
    """Issues filtered by customer slug, assignee login (`none` = unassigned) and
    minimum idle days, most idle first."""
    if state not in ("open", "closed", "all"):
        return {"error": f"state must be open, closed or all, got {state!r}"}
    r = _run(build_command(customer, assignee, state, _FETCH_CAP))
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    try:
        rows = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return {"error": f"Could not parse gh output: {r.stdout[:300]}"}
    if stage and stage.lower() not in ("get", "analyze", "ship", "done"):
        return {"error": f"stage harus Get, Analyze, Ship atau Done, bukan {stage!r}"}
    return shape_issues(rows, datetime.now(timezone.utc), idle_days, limit, stage)
