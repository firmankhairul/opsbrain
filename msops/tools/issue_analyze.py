"""Analyze in one call: owner, classification, action items, banner and board together.

Analyze was three or four separate calls (issue_assign, issue_classify, a hand-edited
action-items table, issue_set_board_fields), and the step that got skipped was usually one
of them: #460 had its items worked and its weight typed by hand, so the board never got a
Segment. One dry-run shows the whole result; one approval writes it.

The pieces stay what they were: the weight and scope come from the same table and checks as
issue_classify, the decision is recorded in the same `Klasifikasi` comment the board's
Segment is derived from, and the board is mirrored by sync_board.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from msops.tools import stage
from msops.tools.board import sync_board
from msops.tools.integrations import REPO, _ensure_label, get_issue
from msops.tools.issue_classify import apply_lines, classify_issue
from msops.tools.issue_resolve import assign_issue
from msops.tools.issue_write import TableError, _next_open, _refresh_banner, _run, parse_action_items

_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌]")
_PLACEHOLDER = re.compile(r"analisa dan usulkan action item", re.IGNORECASE)


def _cell(text: str) -> str:
    return " ".join(str(text).replace("|", "/").split())


def parse_actions(actions: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """`"Action | PIC"` strings -> (action, pic) pairs. PIC defaults to Example MSP."""
    rows, bad = [], []
    for i, raw in enumerate(actions or [], 1):
        text, _, pic = (raw or "").partition("|")
        text, pic = _cell(text), _cell(pic) or "Example MSP"
        if not text:
            bad.append(f"action {i} kosong")
        elif _EMOJI.search(text + pic):
            bad.append(f"action {i} berisi emoji")
        else:
            rows.append((text, pic))
    if not rows and not bad:
        bad.append("actions wajib: minimal satu 'Action | PIC'")
    return rows, bad


def replace_placeholder_table(body: str, rows: list[tuple[str, str]]) -> str:
    """Swap the intake placeholder table for the analysed action items.

    Only a placeholder-only table is replaced: a table with real rows holds progress, and
    overwriting it is exactly the loss the move-don't-delete rule forbids.
    """
    table = parse_action_items(body)
    real = [n for n, r in table["rows"].items() if not _PLACEHOLDER.search(r["cells"][1])]
    if real:
        raise TableError(f"tabel sudah berisi action item {real}; ubah lewat "
                         "issue_update_action_item atau issue_rewrite_body")
    lines = body.splitlines()
    new = ["| # | Action | PIC | Status |", "|---|--------|-----|--------|",
           *[f"| {i} | {a} | {p} | Pending |" for i, (a, p) in enumerate(rows, 1)]]
    header = next(i for i in range(table["start"] + 1, table["end"] + 1)
                  if lines[i].strip().startswith("|"))
    return "\n".join(lines[:header] + new + lines[table["end"] + 1:])


def analyze_issue(number: int, task_type: str, env: str, actions: list[str],
                  priority: Optional[str] = None, scope: Optional[str] = None,
                  scope_reason: Optional[str] = None, kind: str = "bau",
                  login: Optional[str] = None, dry_run: bool = True,
                  today: Optional[str] = None) -> dict:
    rows, bad = parse_actions(actions)
    if bad:
        return {"error": "analisa ditolak — " + " · ".join(bad)}
    iss = get_issue(number)
    if "error" in iss:
        return {"error": iss["error"]}
    if not iss.get("assignees") and not (login or "").strip():
        return {"error": f"#{number} belum punya pemilik — isi login (owner) di panggilan ini"}

    cls = classify_issue(number, task_type, env, priority=priority, scope=scope,
                         scope_reason=scope_reason, dry_run=True, kind=kind, today=today)
    if "error" in cls:
        return {"error": cls["error"], "step": "klasifikasi"}

    stamp = today or date.today().isoformat()
    body = apply_lines(iss.get("body") or "", cls["weight_line"], cls.get("scope_line"))
    try:
        body = replace_placeholder_table(body, rows)
        table = parse_action_items(body)
    except TableError as e:
        return {"error": f"tabel Action items: {e}", "step": "action items"}
    note = f"analisa selesai: {task_type} × {env}, {len(rows)} action item"
    lines = _refresh_banner(body.splitlines(), stamp, note, _next_open(table), table, "in_progress")
    owners = iss.get("assignees") or [{"login": login.strip().lstrip("@")}]
    st = stage.stage_for_issue({**iss, "assignees": owners}, "\n".join(lines))
    body = stage.apply("\n".join(lines), st)

    items = "\n".join(f"{i}. {a} ({p})" for i, (a, p) in enumerate(rows, 1))
    comment = cls["comment_preview"].rstrip() + f"\n\n**Action items hasil analisa:**\n\n{items}\n"
    result = {"issue": number, "dry_run": dry_run, "url": iss.get("url"),
              "owner": login if login and not iss.get("assignees") else None,
              "weight": cls["weight"], "scope_line": cls.get("scope_line"),
              "labels": cls["labels"], "comment_preview": comment,
              "banner_after": "\n".join(l for l in body.splitlines()[:6] if l.startswith(">")),
              "tahap": st.label, "next": st.next}
    if dry_run:
        result["body_after_preview"] = body[:1500]
        result["board_preview"] = cls["board"]
        return result

    done: list[str] = []
    if result["owner"]:
        a = assign_issue(number, result["owner"], dry_run=False)
        if "error" in a:
            return {**result, "error": f"owner gagal dipasang: {a['error']}", "done": done}
        done.append("owner")
    cr = _run(["gh", "issue", "comment", str(number), "--repo", REPO, "--body-file", "-"],
              stdin=comment)
    if cr.returncode != 0:
        return {**result, "error": f"comment gagal: {cr.stderr.strip()}", "done": done}
    result["comment_url"] = (cr.stdout or "").strip().splitlines()[-1] if cr.stdout.strip() else ""
    done.append("comment")
    er = _run(["gh", "issue", "edit", str(number), "--repo", REPO, "--body-file", "-"], stdin=body)
    if er.returncode != 0:
        return {**result, "error": f"body gagal diperbarui: {er.stderr.strip()}", "done": done}
    done.append("body")
    lab = cls["labels"]
    if lab.get("add"):
        _ensure_label(lab["add"])
        lr = _run(["gh", "issue", "edit", str(number), "--repo", REPO,
                   "--add-label", lab["add"], "--remove-label", lab["remove"]])
        if lr.returncode == 0:
            done.append("label")
    fresh = get_issue(number)
    result["board"] = sync_board(fresh if "error" not in fresh else {**iss, "body": body})
    result["done"] = done
    return result
