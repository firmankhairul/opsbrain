"""Rewrite an issue body without losing what was in it.

For the 116 acme-retail issues that fail the PM test. `issue_update_action_item` maintains an
issue that is already in shape; this is what gets a legacy issue INTO shape.

The hazard is specific and irreversible, in the standard's own words: an overwritten
body cannot be recovered through the API or `gh` — only the current revision is
returned. So "move, don't delete" cannot be a convention here. It is enforced:

  1. ARCHIVE FIRST. The old body is posted as a dated comment before the new one is
     written, in the same call. There is no way to skip it.
  2. IDENTIFIERS THAT LEAVE THE BODY ARE REPORTED, not refused. Verified 2026-10-01:
     GitHub issue search indexes comments, and the archive from guard 1 holds the old
     body verbatim — so every identifier stays findable in the issue by construction.
     Refusing here added no safety and actively fought the goal: it forced 29 ids into
     #154's Environment table, making it 31% of a body that is supposed to be a summary.
     What belongs in the body is what a reader needs to ACT on now; history stays
     searchable in the archive.
  3. IT MUST NOT GET WORSE. The new body is scored against the five PM questions and
     refused if it answers fewer than the old one did.

The summary itself is NOT generated here. A script cannot judge which prose belongs in
`## Masalah` versus `## Catatan` — that conclusion is already recorded in the rollout
plan — so the caller composes the body and this module guarantees the cost of being
wrong stays recoverable.

One issue per call, dry_run by default, no batch mode: a mass rewrite is exactly the
accident worth making impossible.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import json
import re
import subprocess
from datetime import date
from typing import Optional

from msops.tools.issue_audit import audit_body
from msops.tools.board import derive_board_fields, sync_board
from msops.tools.stage import weight_line

REPO = "your-org/ms-ops"

# Things that make an old issue findable years later. Deliberately narrow: a false
# "identifier" would block a legitimate cleanup, so only unambiguous resource shapes.
_IDENTIFIERS = (
    re.compile(r"\bi-[0-9a-f]{8,17}\b"),            # EC2 instance
    re.compile(r"\bami-[0-9a-f]{8,17}\b"),          # AMI
    re.compile(r"\bvol-[0-9a-f]{8,17}\b"),          # EBS volume
    re.compile(r"\bsnap-[0-9a-f]{8,17}\b"),         # snapshot
    re.compile(r"\bsg-[0-9a-f]{8,17}\b"),           # security group
    re.compile(r"\b(?:subnet|vpc|tgw|eni)-[0-9a-f]{8,17}\b"),
    re.compile(r"\b(?:SR[DP]APP\d{6}|SRV[A-Z0-9-]{4,})\b"),   # cmdbid hostname
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),     # IPv4
    re.compile(r"\b\d{12}\b"),                      # AWS account id
)


def _run(cmd: list[str], stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, input=stdin)


def identifiers(text: str) -> set[str]:
    """Every findability-critical token in a body."""
    out: set[str] = set()
    for rx in _IDENTIFIERS:
        out.update(rx.findall(text or ""))
    return out


def _pm_unanswered(number: int, state: str, body: str) -> list[str]:
    for f in audit_body(number, "", state, body)["findings"]:
        if f["severity"] == "pm-insufficient":
            return f["unanswered"]
    return []


def archive_comment(old_body: str, reason: str, stamp: str) -> str:
    """The old body, verbatim, wrapped so the thread stays readable.

    `<details>` keeps a 470-line archive from burying the comments around it while
    still holding every byte.
    """
    return (f"## {stamp} — ARSIP: body versi lama\n\n"
            f"{reason.strip()}\n\n"
            "Disimpan utuh di bawah — body baru adalah ringkasan, dan ini jejak "
            "lengkapnya.\n\n"
            "<details><summary>Body sebelum dirapikan "
            f"({len(old_body.splitlines())} baris)</summary>\n\n"
            f"{old_body}\n\n</details>\n")


def split_detail_to_comment(number: int, title: str, content: str,
                            dry_run: bool = True,
                            today: Optional[str] = None) -> dict:
    """Post a block of detail as its own comment and return the URL to link it from.

    The pattern this encodes came out of tidying #154 by hand: nine AMI and volume ids
    sat in `## Environment` purely because action items 9 and 10 would eventually need
    them. Moving them into a dated inventory comment and linking that comment from those
    two rows took `## Environment` from 18 lines to 7, and the ids stayed one click away
    for whoever executes the work.

    Returns {"url", ...}. The caller puts that url in the action-item row — the row
    reads as the action, the link carries the inventory. Anything repeated in the body
    afterwards is duplication, which is what this exists to avoid.

    This does NOT touch the body; `issue_rewrite_body` does that, in a second call, once the
    url is known.
    """
    if not content.strip():
        return {"error": "content kosong — tidak ada yang dipindahkan"}
    stamp = today or date.today().isoformat()
    body = f"## {stamp} — {title.strip()}\n\n{content.strip()}\n"
    out = {"issue": number, "title": title, "dry_run": dry_run,
           "lines": len(body.splitlines())}
    if dry_run:
        out["preview"] = body[:600]
        out["next_step"] = ("jalankan dry_run=False, lalu pasang url hasilnya ke baris "
                            "Action items lewat issue_rewrite_body")
        return out
    r = _run(["gh", "issue", "comment", str(number), "--repo", REPO, "--body-file", "-"],
             stdin=body)
    if r.returncode != 0:
        return {**out, "error": r.stderr.strip()}
    out["url"] = (r.stdout or "").strip().splitlines()[-1] if r.stdout.strip() else ""
    return out


def update_issue(number: int, body: Optional[str] = None, comment: Optional[str] = None,
                 reason: str = "Dirapikan ke format 5 blok "
                               "(docs/standards/ops-issue-format.md).",
                 dry_run: bool = True, force: bool = False,
                 today: Optional[str] = None) -> dict:
    """Replace an issue body, archiving the old one first. One issue per call.

    number:  the issue to rewrite
    body:    the new body, composed by the caller. Omit to only post a comment.
    comment: an extra comment to post (posted whether or not `body` is given)
    reason:  one line explaining the rewrite, shown at the top of the archive comment
    dry_run: True returns the preview and writes nothing (default)
    force:   proceed despite a dropped identifier or a worse PM score. Use only when
             the loss is intentional and stated — the archive comment still holds the
             old body either way.

    Refuses by default when the new body answers fewer of the five PM questions than
    the old one did — a cleanup that makes an issue less informative is not a cleanup.
    Identifiers leaving the body are reported, not refused: the archive keeps them and
    GitHub search reaches into comments.
    """
    if body is None and comment is None:
        return {"error": "tidak ada yang dikerjakan — beri `body`, `comment`, atau keduanya"}

    r = _run(["gh", "issue", "view", str(number), "--repo", REPO,
              "--json", "number,title,state,body,url,labels,comments"])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    iss = json.loads(r.stdout)
    old_body = iss.get("body") or ""
    state = iss.get("state", "")
    stamp = today or date.today().isoformat()

    out: dict = {"issue": number, "title": iss.get("title", ""), "state": state,
                 "dry_run": dry_run, "url": iss.get("url")}

    if body is None:
        out["body_untouched"] = True
        if not dry_run:
            cr = _run(["gh", "issue", "comment", str(number), "--repo", REPO,
                       "--body-file", "-"], stdin=comment)
            if cr.returncode != 0:
                return {**out, "error": cr.stderr.strip()}
            out["comment_url"] = (cr.stdout or "").strip().splitlines()[-1:]
        else:
            out["comment_preview"] = (comment or "")[:400]
        return out

    # --- guard 2: identifiers must survive
    lost = sorted(identifiers(old_body) - identifiers(body))
    # --- guard 3: it must not get worse
    before = _pm_unanswered(number, state, old_body)
    after = _pm_unanswered(number, state, body)

    out.update({
        "lines_before": len(old_body.splitlines()),
        "lines_after": len(body.splitlines()),
        "pm_unanswered_before": before,
        "pm_unanswered_after": after,
        "identifiers_dropped": lost,
    })

    # Reported, not blocking: the archive holds the old body verbatim and GitHub search
    # indexes comments, so these remain findable. Surfaced so the author can confirm
    # that each one is history rather than something a reader still needs to act on.
    if lost:
        out["identifiers_moved_to_comments"] = (
            f"{len(lost)} identifier keluar dari body ke comment (tetap tercari lewat "
            f"GitHub search): "
            + ", ".join(lost[:8]) + (" …" if len(lost) > 8 else ""))

    blockers = []
    # The weight is a classification, not prose: it carries the task type the board's
    # Segment is derived from. Typed by hand it skips that record (#460 got "4,5" over a
    # TBD where the table gives 5), so once a body has the line only issue_classify
    # changes it. A legacy body without the line may gain one: bringing old issues into
    # shape is what this tool is for.
    old_w, new_w = weight_line(old_body), weight_line(body)
    if old_w is not None and new_w != old_w:
        blockers.append(f"baris Bobot kerja berubah ({old_w or 'tidak ada'} -> "
                        f"{new_w or 'tidak ada'}); bobot hanya diubah lewat issue_classify, "
                        "salin baris lamanya apa adanya")
    if len(after) > len(before):
        blockers.append(f"body baru menjawab LEBIH SEDIKIT pertanyaan PM "
                        f"({5 - len(after)}/5 vs {5 - len(before)}/5): {', '.join(after)}")
    if blockers:
        out["blockers"] = blockers
        if not force:
            out["error"] = ("ditolak — " + " · ".join(blockers)
                            + ". Perbaiki body-nya, atau panggil dengan force=True kalau "
                              "kehilangan itu memang disengaja.")
            return out
        out["forced"] = True

    arc = archive_comment(old_body, reason, stamp)
    out["archive_preview"] = arc[:300]

    if dry_run:
        out["body_preview"] = body[:800]
        out["board_preview"] = derive_board_fields(iss, body)
        out["plan"] = ["posting comment arsip (body lama, utuh)",
                       "tulis body baru",
                       *(["posting comment tambahan"] if comment else [])]
        return out

    # --- guard 1: archive BEFORE writing. Order is the guarantee: if the body write
    # fails, the old content is already preserved in the thread.
    cr = _run(["gh", "issue", "comment", str(number), "--repo", REPO, "--body-file", "-"],
              stdin=arc)
    if cr.returncode != 0:
        return {**out, "error": f"arsip gagal diposting, body TIDAK diubah: {cr.stderr.strip()}"}
    out["archive_url"] = (cr.stdout or "").strip().splitlines()[-1] if cr.stdout.strip() else ""

    er = _run(["gh", "issue", "edit", str(number), "--repo", REPO, "--body-file", "-"],
              stdin=body)
    if er.returncode != 0:
        return {**out, "error": f"body gagal ditulis, tapi arsip sudah aman di "
                                f"{out['archive_url']}: {er.stderr.strip()}"}
    out["body_written"] = True

    if comment:
        _run(["gh", "issue", "comment", str(number), "--repo", REPO, "--body-file", "-"],
             stdin=comment)
    out["board"] = sync_board(iss, body)
    return out
