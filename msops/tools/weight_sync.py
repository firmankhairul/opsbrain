"""Mirror `Bobot kerja` from issue bodies onto the project board's Weight field.

The standard makes markdown canonical and the board a sortable mirror. GitHub Projects
Insights reads the BOARD, so a weight that exists only in markdown is invisible to every
chart built there.

Measured on acme-retail, 2026-10-05: **11 issues carried a weight in the body and none
on the board, worth 98**. A capacity chart built on that board reports 230 where the
real figure is 328 — wrong by 30%, with nothing to indicate it. The two sources had zero
conflicting values and nothing board-only, so markdown was a strict superset; the gap was
purely un-mirrored.

One direction only. Writing markdown from the board would turn the mirror into a second
source, which is the duplication the standard exists to prevent.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import json
import subprocess
from typing import Optional

from msops.tools.board import board_number, set_board_fields
from msops.tools.weight_report import parse_weight

REPO = "your-org/ms-ops"
OWNER = "your-org"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def plan_sync(issues: list[dict], board: dict[int, Optional[float]]) -> dict:
    """Decide what to mirror, without touching anything. Pure, so it is testable.

    `board` maps issue number -> its current Weight (None when empty). A number absent
    from the mapping is not on the board at all, which is reported rather than fixed:
    `issue_set_board_fields` would add it, but doing that silently across a whole customer
    would quietly reshape someone's board.
    """
    to_sync, conflicts = [], []
    matching, not_on_board, no_weight = [], [], []
    for i in issues:
        n = i["number"]
        w, state = parse_weight(i.get("body"))
        if state != "ok":
            no_weight.append(n)
            continue
        if n not in board:
            not_on_board.append(n)
            continue
        cur = board[n]
        if cur == w:
            matching.append(n)
            continue
        if cur is not None:
            # The standard: if the two disagree, the markdown wins. Reported because a
            # board value that drifted means someone edited the mirror by hand, and they
            # should know it was overwritten.
            conflicts.append({"number": n, "markdown": w, "board": cur})
        to_sync.append({"number": n, "weight": w, "board": cur})
    return {"to_sync": to_sync, "conflicts": conflicts,
            "already_matching": matching, "not_on_board": not_on_board,
            "no_markdown_weight": no_weight}


def _issues(customer: str) -> list[dict] | dict:
    r = _run(["gh", "issue", "list", "--repo", REPO,
              "--label", f"customer:{customer.lower()}", "--state", "all",
              "--limit", "500", "--json", "number,title,body,state"])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    return json.loads(r.stdout or "[]")


def _board_weights(board: int) -> dict[int, Optional[float]] | dict:
    r = _run(["gh", "project", "item-list", str(board), "--owner", OWNER,
              "--limit", "500", "--format", "json"])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    out: dict[int, Optional[float]] = {}
    for it in json.loads(r.stdout or "{}").get("items", []):
        c = it.get("content") or {}
        if c.get("type") == "Issue" and c.get("number") is not None:
            out[c["number"]] = it.get("weight")
    return out


def sync_weight_to_board(customer: str, dry_run: bool = True) -> dict:
    """Copy each issue's `Bobot kerja` onto its board Weight field.

    customer: registry slug — the board comes from its `customer.yaml`
    dry_run:  True returns the plan and writes nothing (default)

    Only the Weight field is touched; Status and Segment are not ours to set here.
    Issues with no numeric weight are skipped, which correctly includes umbrellas — the
    standard leaves those unweighted because their children carry it. Issues absent from
    the board are reported, not added.

    Per-issue results, so one failure does not hide behind a single status.
    """
    board = board_number(customer)
    if board is None:
        return {"error": f"{customer} tidak punya `github_project:` di customer.yaml — "
                         "hanya 4 dari 46 customer punya board"}

    issues = _issues(customer)
    if isinstance(issues, dict):
        return issues
    weights = _board_weights(board)
    if "error" in weights:
        return weights

    plan = plan_sync(issues, weights)
    out = {"customer": customer, "board": board, "dry_run": dry_run,
           "issues_scanned": len(issues), **plan}
    out["summary"] = (
        f"{len(plan['to_sync'])} akan disinkronkan "
        f"(bobot {sum(x['weight'] for x in plan['to_sync'])}), "
        f"{len(plan['already_matching'])} sudah sama, "
        f"{len(plan['not_on_board'])} belum di board, "
        f"{len(plan['no_markdown_weight'])} tanpa bobot di markdown")
    if plan["conflicts"]:
        out["warning"] = (f"{len(plan['conflicts'])} issue: nilai board BEDA dari "
                          f"markdown dan akan ditimpa — markdown canonical")
    if dry_run:
        return out

    synced, failed = [], []
    for item in plan["to_sync"]:
        r = set_board_fields(customer, item["number"], weight=item["weight"],
                             dry_run=False)
        if r.get("ok"):
            synced.append(item["number"])
        else:
            failed.append({"number": item["number"],
                           "error": r.get("error") or r.get("results")})
    out["synced"] = synced
    out["failed"] = failed
    out["ok"] = not failed
    return out
