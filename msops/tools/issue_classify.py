"""Classify an issue after analysis: weight, scope, board — the Analyze half of what the
ticket-file flow used to do at creation.

`issue_create` records facts (symptom, impact, requester) and leaves `Bobot kerja: TBD`,
because the weight is a judgement that comes out of the analysis. This is where that
judgement is written down, with the SAME formula the ticket flow uses (`artifacts._weight_line`),
so an issue born on GitHub and one born from a ticket file weigh the same.

What it changes in the issue, and nothing else:
  - the `> **Bobot kerja:**` banner line (replaced, or inserted when missing)
  - the `> **Scope:**` banner line and the `scope:*` label, only for a customer whose
    customer.yaml names a `sow:` (`scope.has_sow`)
  - board Weight and Segment, when the customer has a board; never fails the call
  - one dated ACTION comment with the decision, so the trail shows who decided what

Nothing is inferred: `env` and `priority` are typed by a human, scope comes from reading the
contract (`scope_candidates`), and `dry_run=True` shows everything first. Only two banner
lines move, so no archive comment is posted: the old body is not lost, it is extended.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional

from msops.tools.artifacts import _BASE_WEIGHT, _weight_line
from msops.tools.integrations import REPO, _board_segment, _ensure_label, get_issue
from msops.tools.issue_write import _run  # accepts stdin, integrations._run does not
from msops.tools.scope import IN_SOW, OUT_OF_SOW, has_sow, scope_label, scope_line
from msops.tools.stage import apply as stage_apply, stage_for_issue

_ROOT = Path(__file__).resolve().parents[2]
TASK_TYPES = ("check", "kb", "change-low", "assessment", "change-high", "incident")
_WEIGHT = re.compile(r"^>\s*\*\*Bobot kerja:\*\*.*$", re.MULTILINE)
_SCOPE = re.compile(r"^>?\s*\*\*Scope:\*\*.*$", re.MULTILINE)
_WEIGHT_NUM = re.compile(r"\*\*Bobot kerja:\*\*\s*(\d+)")


def validate(task_type: str, env: str, priority: Optional[str], scope: Optional[str],
             scope_reason: Optional[str], gated: bool) -> list[str]:
    out = []
    if task_type not in TASK_TYPES:
        out.append(f"type harus salah satu dari {', '.join(TASK_TYPES)}")
    if env not in ("prod", "non-prod"):
        out.append("env harus prod atau non-prod (tidak ditebak dari judul)")
    if task_type == "incident" and priority not in ("P1", "P2", "P3", "P4"):
        out.append("insiden butuh priority P1..P4 (penilaian dampak bisnis, bukan kata kunci)")
    if gated:
        if scope not in (IN_SOW, OUT_OF_SOW):
            out.append(f"customer ini punya SoW: isi scope={IN_SOW!r} atau {OUT_OF_SOW!r} "
                       "setelah membaca klausanya (scope_candidates)")
        elif scope == OUT_OF_SOW and not (scope_reason or "").strip():
            out.append("scope out-of-sow wajib menyebut klausanya di scope_reason")
    elif scope:
        out.append("customer ini tidak punya sow: di customer.yaml; scope diabaikan, jangan diisi")
    return out


def apply_lines(body: str, weight_line: str, scope_text: Optional[str]) -> str:
    """Replace or insert the banner lines. Only those lines change."""
    weight_line = weight_line.rstrip("\n")
    if _WEIGHT.search(body):
        body = _WEIGHT.sub(lambda _: weight_line, body, count=1)
    else:
        lines = body.splitlines()
        i = 0
        while i < len(lines) and lines[i].startswith(">"):
            i += 1
        lines.insert(i, weight_line)
        body = "\n".join(lines)
    if scope_text:
        scope_text = scope_text.rstrip("\n")
        if _SCOPE.search(body):
            body = _SCOPE.sub(lambda _: scope_text, body, count=1)
        else:
            body = body.replace(weight_line, weight_line + "\n" + scope_text, 1)
    return body


def customer_of(issue: dict) -> str:
    return next((l["name"].split(":", 1)[1] for l in issue.get("labels", [])
                 if l["name"].startswith("customer:")), "")


def classify_issue(number: int, task_type: str, env: str, priority: Optional[str] = None,
                   scope: Optional[str] = None, scope_reason: Optional[str] = None,
                   dry_run: bool = True, root: Path = _ROOT,
                   today: Optional[str] = None, kind: str = "bau") -> dict:
    iss = get_issue(number)
    if "error" in iss:
        return {"error": iss["error"]}
    customer = customer_of(iss)
    if not customer:
        return {"error": f"#{number} tidak punya label customer:<slug>; pasang dulu"}
    gated = has_sow(customer, root)
    bad = validate(task_type, env, priority, scope, scope_reason, gated)
    if kind not in ("bau", "project"):
        bad.append("kind harus bau atau project")
    if bad:
        return {"error": "klasifikasi ditolak — " + " · ".join(bad), "customer": customer,
                "sow_gated": gated}

    weight_line = _weight_line(task_type, env, priority)
    m = _WEIGHT_NUM.search(weight_line)
    if not m:
        return {"error": "bobot tidak terhitung dari input ini", "line": weight_line}
    weight = int(m.group(1))
    scope_text = scope_line(scope, scope_reason) if gated else None
    body_after = apply_lines(iss.get("body") or "", weight_line, scope_text)
    st = stage_for_issue(iss, body_after)
    body_after = stage_apply(body_after, st)

    stamp = today or date.today().isoformat()
    pr = f" {priority}" if task_type == "incident" else ""
    decision = f"**Klasifikasi:** {task_type}{pr} × {env} → Bobot kerja {weight}"
    if kind == "project":
        decision += " · proyek (Segment Project; MoP penuh, folder projects/)"
    if gated:
        decision += f"\n\n**Scope:** {scope_text.strip().split('**Scope:**', 1)[1].strip()}"
    comment = f"## {stamp} — ACTION\n\n{decision}\n"

    labels = {"add": scope_label(scope) if gated else None,
              "remove": scope_label(IN_SOW if scope == OUT_OF_SOW else OUT_OF_SOW) if gated else None}
    # A project (sustained, multi-deliverable work with its own folder under
    # <slug>/projects/) is grouped on the board as Project whatever its type; its MoPs
    # are full documents, never MoP-lite (SOP: Pekerjaan biasa vs proyek).
    segment = "Project" if kind == "project" else _board_segment(task_type)
    result = {"issue": number, "customer": customer, "dry_run": dry_run, "weight": weight,
              "weight_line": weight_line.strip(), "scope_line": (scope_text or "").strip() or None,
              "labels": labels, "board": {"weight": weight, "segment": segment},
              "comment_preview": comment, "url": iss.get("url"),
              "tahap": st.label, "next": st.next}
    if dry_run:
        return result

    cr = _run(["gh", "issue", "comment", str(number), "--repo", REPO, "--body-file", "-"],
              stdin=comment)
    if cr.returncode != 0:
        return {**result, "error": f"gagal posting comment: {cr.stderr.strip()}"}
    result["comment_url"] = (cr.stdout or "").strip().splitlines()[-1] if cr.stdout.strip() else ""
    er = _run(["gh", "issue", "edit", str(number), "--repo", REPO, "--body-file", "-"],
              stdin=body_after)
    if er.returncode != 0:
        return {**result, "error": f"comment terposting, body gagal diperbarui: {er.stderr.strip()}"}
    if gated:
        _ensure_label(labels["add"])
        lr = _run(["gh", "issue", "edit", str(number), "--repo", REPO,
                   "--add-label", labels["add"], "--remove-label", labels["remove"]])
        result["labels"]["applied"] = lr.returncode == 0
    from msops.tools.board import board_number, set_board_fields
    if board_number(customer) is not None:
        try:
            br = set_board_fields(customer, number, weight=weight, segment=segment, dry_run=False)
            result["board"]["applied"] = bool(br.get("ok"))
            if not br.get("ok"):
                result["board"]["error"] = br.get("error") or br.get("results")
        except Exception as e:  # noqa: BLE001 - the board must never undo the classification
            result["board"]["error"] = f"{type(e).__name__}: {e}"
    else:
        result["board"]["applied"] = False
        result["board"]["note"] = "customer tidak punya board"
    return result
