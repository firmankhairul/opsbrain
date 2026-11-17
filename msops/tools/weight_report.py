"""Aggregate work weight for capacity planning.

The point of the weight table was never tidiness — it was to be able to say how much
work a period actually held. Everything needed for that now exists: `closedAt` comes
from the API, assignees were already in use on 169 of 345 issues, and `Bobot kerja` is
computed at intake. This is the piece that adds it up.

Three things it refuses to do quietly, because a capacity number that is wrong without
saying so is worse than no number:

  - An unfilled `<n>` placeholder is REPORTED, not skipped. The aggregation regex wants a
    digit, so a placeholder silently removes an issue from the total — 88 migrated
    tickets sat in that state, and the gap was invisible until someone went looking.
  - Issues with no assignee are counted in the total but listed separately. Per-person
    capacity from data where half the rows name nobody is not capacity planning.
  - Two logins that are the same person are only merged when an alias map says so
    (`zakinurw` / `zakinw` looked like one person split across two accounts). Guessing
    would quietly halve somebody's load.

Weighting rules it honours, from docs/standards/ops-issue-format.md: an umbrella is not
weighted on its own (its children carry it), and cross-issue work is weighted once at
the umbrella. Both fall out of reading the weight line rather than being special-cased —
an issue with no weight line contributes nothing.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import json
import re
import subprocess
from collections import defaultdict
from typing import Optional

from msops.tools.board import board_number

REPO = "your-org/ms-ops"

# The canonical form, per the standard: the number comes immediately after the label.
_WEIGHT = re.compile(r"\*\*Bobot kerja:?\*\*\s*(\d+)", re.IGNORECASE)
# A weight line that exists but was never filled. Distinguished from "no weight line at
# all" because the two mean different things: forgotten versus deliberately unweighted.
_WEIGHT_ANY = re.compile(r"\*\*Bobot kerja:?\*\*\s*(.+)", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"<\s*n\s*>|<jenis>|<insiden", re.IGNORECASE)

# People with more than one GitHub login. Only merged when stated — guessing would
# quietly halve someone's load, and splitting it would make them look idle.
ALIASES: dict[str, str] = {}


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _canon(login: str) -> str:
    return ALIASES.get(login, login)


_SUB_ISSUES_QUERY = """
query($q: String!, $endCursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $endCursor) {
    pageInfo { hasNextPage endCursor }
    nodes { ... on Issue { number subIssues(first: 1) { totalCount } } }
  }
}
"""


def _sub_issue_counts(customer: str) -> dict[int, int]:
    """issue number -> number of native sub-issues.

    Used to tell an umbrella apart from a forgotten weight. The standard says an
    umbrella is not weighted on its own — its children carry it — so a missing weight
    line there is CORRECT. Before this, both landed in the same bucket, and the worklist
    handed to an engineer mixed "fill this in" with "leave this alone": 5 of the 30
    acme-retail issues flagged as needing a weight were umbrellas.

    One paginated GraphQL call for the whole customer. Returns {} on failure, which
    degrades to the old behaviour (everything looks forgotten) rather than crashing a
    report someone is waiting on.
    """
    r = _run(["gh", "api", "graphql", "--paginate", "--slurp",
              "-F", f"q=repo:{REPO} label:customer:{customer.lower()} is:issue",
              "-f", f"query={_SUB_ISSUES_QUERY}"])
    if r.returncode != 0:
        return {}
    try:
        pages = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return {}
    out: dict[int, int] = {}
    for page in pages:
        for n in (page.get("data", {}).get("search", {}).get("nodes") or []):
            if n and n.get("number") is not None:
                out[n["number"]] = (n.get("subIssues") or {}).get("totalCount", 0)
    return out


def _segments(customer: str) -> dict[int, str]:
    """issue number -> board `Segment`, or {} when the customer has no board.

    Segment lives on the project board, NOT on a label. A first version read it from a
    `segment:` label and every issue came back "(tanpa segment)" — the only label in
    this repo is `customer:<slug>`. Only 4 of 46 customers have a board, so an empty map
    is a normal answer and the report falls back to one bucket.
    """
    board = board_number(customer)
    if board is None:
        return {}
    r = _run(["gh", "project", "item-list", str(board), "--owner", "your-org",
              "--limit", "500", "--format", "json"])
    if r.returncode != 0:
        return {}
    try:
        items = json.loads(r.stdout or "{}").get("items", [])
    except json.JSONDecodeError:
        return {}
    out = {}
    for it in items:
        c = it.get("content") or {}
        if c.get("type") == "Issue" and c.get("number") is not None:
            out[c["number"]] = (it.get("segment") or "").strip() or "(tanpa segment)"
    return out


def parse_weight(body: str) -> tuple[Optional[int], str]:
    """Return (weight, state) for one body.

    state is "ok", "placeholder" (a line exists but was never filled) or "absent" (no
    line at all). The distinction matters: a placeholder is someone forgetting, and
    absent is usually an umbrella that is deliberately unweighted.
    """
    body = body or ""
    m = _WEIGHT.search(body)
    if m:
        return int(m.group(1)), "ok"
    any_line = _WEIGHT_ANY.search(body)
    if any_line and _PLACEHOLDER.search(any_line.group(1)):
        return None, "placeholder"
    if any_line:
        return None, "unparseable"
    return None, "absent"


def report_work_weight(customer: str, period: Optional[str] = None,
                       state: str = "closed") -> dict:
    """Total work weight for a customer, grouped by assignee and by segment label.

    customer: registry slug (drives the `customer:<slug>` label)
    period:   "YYYY-MM" — filters on when the issue CLOSED, which is when the work
              landed. Omit for all time.
    state:    "closed" (default, what a period report means), "open", or "all"

    Returns totals plus the gaps that would otherwise distort them: issues whose weight
    is an unfilled placeholder, and issues with no assignee.
    """
    if period and not re.fullmatch(r"\d{4}-\d{2}", period):
        return {"error": f"period harus YYYY-MM, bukan {period!r}"}

    cmd = ["gh", "issue", "list", "--repo", REPO,
           "--label", f"customer:{customer.lower()}",
           "--state", "all" if state == "all" else state,
           "--limit", "500", "--json",
           "number,title,body,state,assignees,closedAt"]
    r = _run(cmd)
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    issues = json.loads(r.stdout or "[]")

    if period:
        # Filtered on close date, not creation: capacity is about when work landed. An
        # issue still open has not landed, so a period report excludes it by definition.
        issues = [i for i in issues
                  if (i.get("closedAt") or "").startswith(period)]

    by_person: dict[str, int] = defaultdict(int)
    by_person_n: dict[str, int] = defaultdict(int)
    by_segment: dict[str, int] = defaultdict(int)
    segments = _segments(customer)
    total = 0
    placeholders, unassigned = [], []
    umbrellas, forgotten = [], []
    subs = _sub_issue_counts(customer)

    for i in issues:
        w, st = parse_weight(i.get("body"))
        row = {"number": i["number"], "title": (i.get("title") or "")[:70]}
        if st == "placeholder":
            placeholders.append(row)
            continue
        if st in ("absent", "unparseable"):
            # An umbrella with no weight line is correct; a leaf with none is a gap.
            if subs.get(i["number"], 0) > 0:
                umbrellas.append({**row, "sub_issues": subs[i["number"]]})
            else:
                forgotten.append({**row, "state": st})
            continue

        total += w
        people = [_canon(a["login"]) for a in i.get("assignees") or []]
        if not people:
            unassigned.append({**row, "weight": w})
            by_person["(tanpa assignee)"] += w
            by_person_n["(tanpa assignee)"] += 1
        else:
            # Split across co-assignees rather than counted per person, so two names on
            # one issue cannot inflate the total past what was actually done.
            share = w / len(people)
            for p in people:
                by_person[p] += share
                by_person_n[p] += 1

        by_segment[segments.get(i["number"], "(tidak di board)")] += w

    return {
        "customer": customer,
        "period": period or "semua waktu",
        "state": state,
        "issues_counted": len(issues) - len(placeholders) - len(umbrellas)
                          - len(forgotten),
        "total_weight": total,
        "by_assignee": {k: round(v, 1) for k, v in
                        sorted(by_person.items(), key=lambda kv: -kv[1])},
        "issues_per_assignee": dict(by_person_n),
        "by_segment": dict(sorted(by_segment.items(), key=lambda kv: -kv[1])),
        "gaps": {
            "placeholder_weight": placeholders,
            "weight_forgotten": forgotten,
            "umbrella_unweighted": umbrellas,
            "no_assignee": unassigned,
        },
        "warnings": _warnings(placeholders, unassigned, forgotten, umbrellas, total),
    }


def _warnings(placeholders, unassigned, forgotten, umbrellas, total) -> list[str]:
    """Say out loud what would distort the number, rather than printing it clean."""
    out = []
    if placeholders:
        out.append(f"{len(placeholders)} issue punya `Bobot kerja` yang masih "
                   f"placeholder — TIDAK masuk total {total}. Itu sebabnya angka ini "
                   f"bisa lebih rendah dari kerja sebenarnya.")
    if unassigned:
        w = sum(x["weight"] for x in unassigned)
        out.append(f"{len(unassigned)} issue tanpa assignee menyumbang bobot {w} — "
                   f"masuk total tapi tidak bisa dibagi per orang.")
    if forgotten:
        out.append(f"{len(forgotten)} issue tanpa baris `Bobot kerja` dan bukan "
                   f"umbrella — ini yang perlu diisi.")
    if umbrellas:
        out.append(f"{len(umbrellas)} umbrella tidak dibobot, dan itu BENAR — anaknya "
                   f"yang membawa bobot. Tidak perlu diisi.")
    if not ALIASES:
        out.append("Peta alias kosong. Kalau ada orang dengan dua akun GitHub, "
                   "kapasitasnya terpecah — isi ALIASES di weight_report.py.")
    return out
