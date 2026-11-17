"""Maintain a GitHub Issue body as work progresses.

This is the maintainer the 5-block standard needs. Shape is cheap; keeping it true is
what was missing — #316 was accurate only because a human curated it by hand once, and
it would have gone stale again the moment items 7 and 8 were worked.

The insight is that three things change on different clocks, and conflating them is what
produced the staleness in #316 and #343:

  action-item row  state of one item        one line, forever
  status banner    latest movement          OVERWRITTEN, never grows
  comment          what happened, evidence  APPENDED, never rewritten

So progress grows the comment thread and never the body. A body stays ~40 lines no
matter how much work happens, which is what keeps it readable at a sync-up.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import json
import re
import subprocess
from datetime import date
from typing import Optional

from msops.tools import banner, stage
from msops.tools.board import derive_board_fields, sync_board
from msops.tools.action_status import STATES, is_done

REPO = "your-org/ms-ops"

# The 4 states from the standard's writing conventions live in action_status. `done`
# stamps a date because "when" is one of the five questions a PM asks.
_STATES = STATES

# A dependency already written by hand in #319 (`Pending (blok by #9)`). Preserved
# across a status change instead of being clobbered — it is real information.
_DEP = re.compile(r"(?:·\s*)?\(?\bblok(?:\s+by)?\s*(#\d+)\)?", re.IGNORECASE)

# Marker appended to every comment this tool writes, so a later run can count how many
# attempts an item took. That count is the evidence for the "+3 rework" adder in the
# weight table — deriving it beats asking someone to remember.
_MARK = "<!-- ms-ops:action-item={item} status={status} -->"
_MARK_RE = re.compile(r"<!--\s*ms-ops:action-item=(\d+)\s+status=(\w+)\s*-->")

_BANNER_STATUS = banner.STATUS
_BANNER_BOLA = banner.BOLA
_BANNER_NEXT = banner.NEXT
_BANNER_UPDATED = banner.UPDATED
_ALL_DONE_NEXT = stage.ALL_DONE_NEXT
_MD_LINK = re.compile(r"^\[(?P<text>.+)\]\((?P<url>\S+)\)$")


def _run(cmd: list[str], stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, input=stdin)


class TableError(Exception):
    """Raised when the action-items table cannot be parsed with confidence.

    Aborting is the only safe response: a half-understood table edited in place would
    corrupt the one block that IS the progress source of truth.
    """


def _split_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def parse_action_items(body: str) -> dict:
    """Locate the action-items table and index its rows by item number.

    Returns {"header": [...], "status_col": int, "pic_col": int|None,
             "rows": {n: {"line_no", "cells"}}, "start", "end"}.

    Column positions are found from the header rather than assumed, because 29
    acme-retail issues have a table with no PIC column at all.
    """
    lines = body.splitlines()
    start = None
    for i, l in enumerate(lines):
        if re.match(r"^#{2,3}\s*action items\s*$", l.strip(), re.IGNORECASE):
            start = i
            break
    if start is None:
        raise TableError("tidak ada heading '## Action items'")

    header = None
    header_no = None
    for i in range(start + 1, min(start + 8, len(lines))):
        if lines[i].strip().startswith("|"):
            header = _split_row(lines[i])
            header_no = i
            break
    if header is None:
        raise TableError("tabel Action items tidak ditemukan setelah heading")

    low = [h.lower() for h in header]
    try:
        status_col = low.index("status")
    except ValueError:
        raise TableError(f"tabel tidak punya kolom Status (header: {header})")
    pic_col = low.index("pic") if "pic" in low else None

    rows: dict[int, dict] = {}
    end = header_no
    for i in range(header_no + 1, len(lines)):
        l = lines[i]
        if not l.strip().startswith("|"):
            if l.strip() == "":
                continue
            break
        end = i
        cells = _split_row(l)
        if re.match(r"^[\s:|-]+$", "|".join(cells)):
            continue
        m = re.match(r"^\d+$", cells[0])
        if not m:
            continue
        if len(cells) <= status_col:
            raise TableError(f"baris {cells[0]} punya {len(cells)} kolom, "
                             f"Status di indeks {status_col}")
        rows[int(cells[0])] = {"line_no": i, "cells": cells}

    if not rows:
        raise TableError("tabel Action items tidak punya baris bernomor")
    return {"header": header, "status_col": status_col, "pic_col": pic_col,
            "rows": rows, "start": start, "end": end}


def _next_open(table: dict) -> Optional[dict]:
    """First row still open, which is what `Next` and `Bola di` are derived from.

    A blocked row still counts as next: it IS what the issue is waiting on, and naming
    the party holding it is the most useful line in the body at a sync-up.
    """
    for n in sorted(table["rows"]):
        cells = table["rows"][n]["cells"]
        if not is_done(cells[table["status_col"]]):
            return {"n": n, "cells": cells}
    return None


def _plain_action(cell: str) -> str:
    """Strip an existing markdown link so re-linking does not nest."""
    m = _MD_LINK.match(cell.strip())
    return m.group("text") if m else cell.strip()


def _count_attempts(comments: list[dict], item: int) -> int:
    n = 0
    for c in comments:
        for mi, ms in _MARK_RE.findall(c.get("body") or ""):
            if int(mi) == item and ms == "in_progress":
                n += 1
    return n


def update_action_item(issue: int, item: int, status: str, note: str,
                       dry_run: bool = True, today: Optional[str] = None,
                       force: bool = False) -> dict:
    """Record progress on one action item of a GitHub Issue.

    One call maintains everything that must stay in step: the row's state, the banner
    (`Update terakhir`, and `Next`/`Bola di` recomputed from the next open row), and a
    dated comment carrying the evidence. On `done` the comment's URL is written back
    into the row, so the evidence link is a by-product of the work rather than a
    discipline — which is why `## Referensi` was dropped.

    issue:   issue number
    item:    row number in `## Action items`
    status:  done | in_progress | blocked | pending | pending_approval
             (blocked = waiting on access or another team -> banner Escalated;
              pending_approval = waiting for an approver -> banner Pending Approval)
    note:    what happened — becomes the comment body and the banner's update line
    dry_run: True returns the preview without writing anything (default)
    force:   pass the Analyze gate: `in_progress` and `done` are refused while `Bobot
             kerja` is still TBD. The bypass is written into the comment.

    Progress that is not completion is the normal case: calling with `in_progress`
    repeatedly leaves the row alone and refreshes the banner + posts a comment. The tool
    counts those attempts and flags the `+3 rework` adder when there is more than one,
    the way #319 earned its weight of 15.
    """
    if status not in _STATES:
        return {"error": f"status harus salah satu dari {sorted(_STATES)}, bukan {status!r}"}
    if not note.strip():
        return {"error": "note wajib — itu yang jadi isi comment dan baris banner"}

    r = _run(["gh", "issue", "view", str(issue), "--repo", REPO,
              "--json", "number,title,state,body,labels,comments,url,assignees"])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    iss = json.loads(r.stdout)
    body = iss.get("body") or ""
    # Work may be filed and analysed without an owner; it may not be completed without one,
    # or the weight lands in the total and nobody's column (121 open issues had no owner on
    # 2026-10-13).
    if status == "done" and not iss.get("assignees"):
        return {"error": f"#{issue} belum punya pemilik — jalankan issue_assign dulu, baru tandai done"}

    # The Analyze gate. Work started before the weight is classified is how an issue ends
    # up with a hand-typed weight and an empty board Segment (#460, 2026-10-15). Waiting
    # states stay open: recording that something is blocked is never skipping a step.
    gated = status in ("in_progress", "done") and stage.weight_tbd(body)
    if gated and not force:
        st = stage.stage_for_issue(iss)
        return {"error": f"#{issue} belum selesai Analyze: Bobot kerja masih TBD. "
                         f"Next: {st.next}. Lewati hanya bila memang perlu: force=True, "
                         "dengan alasannya di note.",
                "tahap": st.label, "next": st.next}

    try:
        table = parse_action_items(body)
    except TableError as e:
        return {"error": f"tabel Action items tidak bisa dibaca: {e}",
                "hint": "perbaiki tabelnya dulu — tool menolak mengedit tabel yang "
                        "tidak dipahami penuh, supaya blok progres tidak rusak"}
    if item not in table["rows"]:
        return {"error": f"item {item} tidak ada; yang ada: {sorted(table['rows'])}"}

    stamp = today or date.today().isoformat()
    attempts = _count_attempts(iss.get("comments") or [], item)

    row = table["rows"][item]
    cells = list(row["cells"])
    old_status = cells[table["status_col"]]
    dep = _DEP.search(old_status)

    new_status = _STATES[status]
    if status == "done":
        new_status += f" {stamp}"
    if dep and status != "done":
        new_status += f" · blok {dep.group(1)}"
    cells[table["status_col"]] = new_status

    bypass = ("**Gerbang Analyze dilewati (force=True):** Bobot kerja masih TBD saat item "
              "ini dikerjakan.\n\n") if gated else ""
    comment = (f"## {stamp} — {'RESOLUTION' if status == 'done' else 'ACTION'}\n\n"
               f"**Action item {item}:** {_plain_action(cells[1])}\n\n{note.strip()}\n\n"
               + bypass + _MARK.format(item=item, status=status))

    result = {
        "issue": issue, "item": item, "status": status, "dry_run": dry_run,
        "row_before": "| " + " | ".join(row["cells"]) + " |",
        "attempts_before": attempts,
        "comment_preview": comment,
    }

    # Repeated attempts are the evidence for the rework adder. Reported, never applied
    # automatically: the weight line is a judgement the standard keeps with a human.
    if status == "done" and attempts > 1:
        result["weight_hint"] = (
            f"item {item} tercatat {attempts}× in_progress — kandidat '+3 rework di luar "
            "prosedur normal' (lihat tabel bobot). Catat alasannya di ## Catatan & keputusan.")

    if not dry_run:
        cr = _run(["gh", "issue", "comment", str(issue), "--repo", REPO, "--body-file", "-"],
                  stdin=comment)
        if cr.returncode != 0:
            return {**result, "error": f"gagal posting comment: {cr.stderr.strip()}"}
        comment_url = (cr.stdout or "").strip().splitlines()[-1] if cr.stdout.strip() else ""
        result["comment_url"] = comment_url
        # Link the evidence into the row only on completion: an in-progress row would
        # accumulate a new link on every attempt.
        if status == "done" and comment_url:
            cells[1] = f"[{_plain_action(cells[1])}]({comment_url})"

    new_row = "| " + " | ".join(cells) + " |"
    lines = body.splitlines()
    lines[row["line_no"]] = new_row
    table["rows"][item]["cells"] = cells

    nxt = _next_open(table)
    lines = _refresh_banner(lines, stamp, note, nxt, table, status)

    # Tahap and Next come from the issue's stage, so a row worked before Analyze is done
    # still reads "Analyze" with the command to run, instead of looking like normal Ship.
    st = stage.stage_for_issue(iss, "\n".join(lines))
    new_body = stage.apply("\n".join(lines), st)
    result["row_after"] = new_row
    result["banner_after"] = "\n".join(l for l in new_body.splitlines()[:5] if l.startswith(">"))
    result["tahap"] = st.label
    result["next"] = st.next
    result["all_done"] = nxt is None
    if nxt is None:
        result["proposal"] = (f"semua action item Done — verifikasi, kirim balasan customer, lalu "
                              f"issue_resolve({issue}, reply_evidence=..., docs_delta=...) untuk "
                              "Resolved + tutup (tidak dilakukan otomatis)")

    if dry_run:
        result["body_after_preview"] = new_body[:1200]
        result["board_preview"] = derive_board_fields(iss, new_body)
        return result

    er = _run(["gh", "issue", "edit", str(issue), "--repo", REPO, "--body-file", "-"],
              stdin=new_body)
    if er.returncode != 0:
        return {**result, "error": f"comment sudah terposting, tapi body gagal diperbarui: "
                                   f"{er.stderr.strip()}"}
    result["url"] = iss.get("url")
    result["board"] = sync_board(iss, new_body)
    return result


def _refresh_banner(lines: list[str], stamp: str, note: str, nxt: Optional[dict],
                    table: dict, status: str) -> list[str]:
    """Rewrite the banner from the table. This is the anti-staleness mechanism.

    `Next` and `Bola di` are DERIVED from the next open row, never typed. A banner that
    is never hand-written cannot drift from the work — which is the defect behind #316.
    The idle-days token is dropped on every update, because the issue just moved.
    """
    # One scannable line. The full note lives in the comment; a banner that wraps
    # defeats the purpose of being readable at a glance.
    first = note.strip().splitlines()[0]
    if len(first) > 90:
        cut = first[:90].rsplit(" ", 1)[0]
        first = cut + " …"
    out = list(lines)

    for i, l in enumerate(out[:6]):
        if not l.startswith(">"):
            continue
        if _BANNER_UPDATED.match(l):
            out[i] = f"> **Update terakhir:** {stamp} — {first}"
            continue
        if "**Status:**" in l:
            if nxt is None:
                # Every row done is not Resolved: the flow still needs verification, the
                # customer reply and the Docs Delta row. issue_resolve writes Resolved.
                l = _BANNER_STATUS.sub(lambda m: m.group(1) + "In Progress ", l, count=1)
            elif status == "pending_approval":
                l = _BANNER_STATUS.sub(lambda m: m.group(1) + "Pending Approval ", l, count=1)
            elif status == "blocked":
                # Blocked by access or another team is waiting on someone else, which the
                # rules call Escalated; Pending Approval was wrong for most blockers.
                l = _BANNER_STATUS.sub(lambda m: m.group(1) + "Escalated ", l, count=1)
            elif status in ("in_progress", "done"):
                # `done` moves it too, not just `in_progress`: a ticket that starts at
                # "Pending Approval" (start_workflow sets that when it writes a MoP) and
                # is then worked item by item would otherwise keep reading "Pending
                # Approval" until the very last one. Something was finished and more
                # remains — that is In Progress.
                l = _BANNER_STATUS.sub(lambda m: m.group(1) + "In Progress ", l, count=1)
            if nxt is not None:
                pic = (nxt["cells"][table["pic_col"]] if table["pic_col"] is not None
                       else "Example MSP")
                l = _BANNER_BOLA.sub(lambda m: m.group(1) + (pic or "Example MSP") + " ", l, count=1)
                l = _BANNER_NEXT.sub(
                    lambda m: m.group(1) + _plain_action(nxt["cells"][1]), l, count=1)
            else:
                l = _BANNER_BOLA.sub(lambda m: m.group(1) + "Example MSP ", l, count=1)
                l = _BANNER_NEXT.sub(lambda m: m.group(1) + _ALL_DONE_NEXT, l, count=1)
            out[i] = re.sub(r"\s+·\s*$", "", l.rstrip())
    return out
