"""Owner and closure of an issue: `issue_assign` and `issue_resolve`.

Two decisions the flow leaves to a person, written down by a tool so they are done the same
way every time:

  - assign: an issue may be filed and analysed without an owner, but it may not be completed
    without one. `issue_update_action_item(status="done")` refuses until this ran.
  - resolve: every row done is not Done. Done is: fix verified, customer reply sent, Docs
    Delta recorded. `issue_resolve` writes those three things, sets the banner to Resolved
    and closes the issue, in one call, with the source of the decision in the comment.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from msops.tools import banner, stage
from msops.tools.integrations import REPO, get_issue
from msops.tools.action_status import is_done
from msops.tools.issue_write import TableError, _run, parse_action_items

_BANNER_STATUS = banner.STATUS
_BOLA = banner.BOLA
_NEXT = banner.NEXT
_UPDATED = banner.UPDATED
_DOCS_DELTA_ROW = re.compile(r"^\|\s*Docs Delta\s*\|.*\|\s*$", re.MULTILINE)
_ENV_HEADING = re.compile(r"^## Environment\s*$", re.MULTILINE)


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "/").split())


def apply_docs_delta(body: str, docs_delta: str) -> str:
    """Set the `Docs Delta` row in the Environment table; add it when missing.

    Without an Environment table (legacy body) the value goes on a banner line, so the
    information is still in the body and still findable."""
    row = f"| Docs Delta | {_cell(docs_delta)} |"
    if _DOCS_DELTA_ROW.search(body):
        return _DOCS_DELTA_ROW.sub(lambda _: row, body, count=1)
    m = _ENV_HEADING.search(body)
    if m:
        lines = body.splitlines()
        start = body[:m.start()].count("\n")
        i = start + 1
        last_row = None
        while i < len(lines) and not lines[i].startswith("## "):
            if lines[i].startswith("|"):
                last_row = i
            elif last_row is not None and lines[i].strip() == "":
                break
            i += 1
        if last_row is not None:
            lines.insert(last_row + 1, row)
            return "\n".join(lines)
    lines = body.splitlines()
    i = 0
    while i < len(lines) and lines[i].startswith(">"):
        i += 1
    lines.insert(i, f"> **Docs Delta:** {_cell(docs_delta)}")
    return "\n".join(lines)


def apply_resolved_banner(body: str, stamp: str, note: str) -> str:
    """Status Resolved, Bola di and Next cleared, Update terakhir stamped. Inserted when absent."""
    first = note.strip().splitlines()[0][:90] if note.strip() else "selesai"
    if _BANNER_STATUS.search(body):
        lines = body.splitlines()
        for i, l in enumerate(lines[:8]):
            if not l.startswith(">"):
                continue
            if _UPDATED.match(l):
                lines[i] = f"> **Update terakhir:** {stamp} — {first}"
                continue
            if "**Status:**" in l:
                l = _BANNER_STATUS.sub(lambda m: m.group(1) + "Resolved ", l, count=1)
                l = _BOLA.sub(lambda m: m.group(1) + "— ", l, count=1)
                l = _NEXT.sub(lambda m: m.group(1) + "—", l, count=1)
                lines[i] = re.sub(r"\s+·\s*$", "", l.rstrip())
        return "\n".join(lines)
    return (f"> **Status:** Resolved · **Bola di:** — · **Next:** —\n"
            f"> **Update terakhir:** {stamp} — {first}\n\n" + body.lstrip("\n"))


def open_rows(body: str) -> Optional[list[int]]:
    """Numbers of action items still open, or None when there is no readable table."""
    try:
        table = parse_action_items(body)
    except TableError:
        return None
    return [n for n, row in sorted(table["rows"].items())
            if not is_done(row["cells"][table["status_col"]])]


def assign_issue(number: int, login: str, dry_run: bool = True) -> dict:
    login = (login or "").strip().lstrip("@")
    if not login:
        return {"error": "login GitHub wajib (tanpa @)"}
    iss = get_issue(number)
    if "error" in iss:
        return {"error": iss["error"]}
    current = [a.get("login") for a in iss.get("assignees") or []]
    result = {"issue": number, "login": login, "assignees_before": current, "dry_run": dry_run,
              "url": iss.get("url")}
    if login in current:
        return {**result, "note": "sudah menjadi pemilik, tidak ada perubahan"}
    if dry_run:
        return result
    r = _run(["gh", "issue", "edit", str(number), "--repo", REPO, "--add-assignee", login])
    if r.returncode != 0:
        return {**result, "error": r.stderr.strip()[:300]}
    after = get_issue(number)
    result["assignees_after"] = [a.get("login") for a in after.get("assignees") or []]
    # The owner is part of Get: the banner's Tahap and Next move on as soon as it is set.
    if "error" not in after:
        body = after.get("body") or ""
        st = stage.stage_for_issue(after)
        refreshed = stage.apply(body, st)
        result["tahap"], result["next"] = st.label, st.next
        if refreshed != body:
            er = _run(["gh", "issue", "edit", str(number), "--repo", REPO, "--body-file", "-"],
                      stdin=refreshed)
            if er.returncode != 0:
                result["banner_note"] = f"owner terpasang, banner belum diperbarui: {er.stderr.strip()[:200]}"
    return result


def resolve_issue(number: int, reply_evidence: str, docs_delta: str, source: str = "",
                  force: bool = False, dry_run: bool = True, today: Optional[str] = None) -> dict:
    if not (reply_evidence or "").strip():
        return {"error": "reply_evidence wajib: kapan dan lewat apa balasan ke customer terkirim "
                         "(atau 'tidak perlu balasan: <alasan>')"}
    if not (docs_delta or "").strip():
        return {"error": "docs_delta wajib: 'diperbarui: <berkas>' atau 'tidak ada perubahan'"}
    iss = get_issue(number)
    if "error" in iss:
        return {"error": iss["error"]}
    body = iss.get("body") or ""
    still_open = open_rows(body)
    if still_open and not force:
        return {"error": f"action item {still_open} masih terbuka — selesaikan dulu lewat "
                         "issue_update_action_item, atau force=True dengan alasan di reply_evidence",
                "open_items": still_open}
    if not iss.get("assignees"):
        return {"error": f"#{number} belum punya pemilik — issue_assign dulu; yang menutup harus tercatat"}

    stamp = today or date.today().isoformat()
    src = (source or "").strip() or "atas instruksi operator sesi ini"
    comment = (f"## {stamp} — RESOLUTION\n\n"
               f"**Balasan customer:** {reply_evidence.strip()}\n\n"
               f"**Docs Delta:** {docs_delta.strip()}\n\n"
               f"**Sumber keputusan:** {src}\n"
               + (f"\n**Catatan:** ditutup dengan force=True, action item {still_open} dicatat terbuka.\n"
                  if still_open else ""))
    new_body = apply_resolved_banner(apply_docs_delta(body, docs_delta), stamp, reply_evidence)
    new_body = stage.apply(new_body, stage.stage_of(new_body, iss.get("assignees") or [], "CLOSED"))
    result = {"issue": number, "dry_run": dry_run, "url": iss.get("url"),
              "comment_preview": comment,
              "banner_after": "\n".join(l for l in new_body.splitlines()[:4] if l.startswith(">")),
              "docs_delta_row": next((l for l in new_body.splitlines() if "Docs Delta" in l), ""),
              "will_close": True, "open_items_forced": still_open or []}
    if dry_run:
        return result
    cr = _run(["gh", "issue", "comment", str(number), "--repo", REPO, "--body-file", "-"], stdin=comment)
    if cr.returncode != 0:
        return {**result, "error": f"gagal posting comment: {cr.stderr.strip()}"}
    result["comment_url"] = (cr.stdout or "").strip().splitlines()[-1] if cr.stdout.strip() else ""
    er = _run(["gh", "issue", "edit", str(number), "--repo", REPO, "--body-file", "-"], stdin=new_body)
    if er.returncode != 0:
        return {**result, "error": f"comment terposting, body gagal diperbarui: {er.stderr.strip()}"}
    cl = _run(["gh", "issue", "close", str(number), "--repo", REPO])
    result["closed"] = cl.returncode == 0
    if cl.returncode != 0:
        result["error"] = f"body Resolved, tapi issue gagal ditutup: {cl.stderr.strip()}"
    customer = next((l["name"].split(":", 1)[1] for l in iss.get("labels", [])
                     if l["name"].startswith("customer:")), "")
    if customer:
        from msops.tools.board import board_number, set_board_fields
        if board_number(customer) is not None:
            try:
                br = set_board_fields(customer, number, status="Done", dry_run=False)
                result["board"] = {"applied": bool(br.get("ok"))}
            except Exception as e:  # noqa: BLE001 - the board must never undo the closure
                result["board"] = {"error": f"{type(e).__name__}: {e}"}
    return result
