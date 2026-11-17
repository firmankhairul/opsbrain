from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from msops.tools.artifacts import (
    create_ticket, create_mop, create_incident_report,
)
from msops.tools.tracker import check_recurrence

CHECK_KEYWORDS = {
    "check", "cek", "verify", "verifikasi", "list", "show", "get",
    "monitor", "lihat", "status", "health", "ping",
}

INCIDENT_KEYWORDS = {
    "outage", "down", "tidak bisa", "error", "gagal", "fail", "crash",
    "unreachable", "timeout", "5xx", "4xx", "alert", "incident",
    "offline", "mati", "tidak jalan",
}

COMPLEX_KEYWORDS = {
    "migrate", "migrasi", "upgrade", "downgrade", "replace",
    "major", "database", "rds", "eks", "cluster", "terraform",
    "architecture", "arsitektur",
}

CHANGE_KEYWORDS = {
    "add", "create", "delete", "remove", "update", "change",
    "tambah", "hapus", "ubah", "ganti", "restart", "reboot",
}


def classify_work(description: str) -> dict:
    desc = description.lower()

    # Read-only if starts with check keyword and no change words
    if any(desc.startswith(k) or f" {k} " in desc for k in CHECK_KEYWORDS):
        if not any(w in desc for w in CHANGE_KEYWORDS):
            return {"type": "check", "risk": "none", "needs_issue": False, "document_hint": None}

    if any(k in desc for k in INCIDENT_KEYWORDS):
        return {"type": "incident", "risk": "high", "needs_issue": True,
                "document_hint": "incident_report bila action item membutuhkannya (ops-rules aturan 9)"}

    if any(k in desc for k in COMPLEX_KEYWORDS):
        return {"type": "change-high", "risk": "high", "needs_issue": True,
                "document_hint": "mop bila ops-rules aturan 9 mewajibkan; cari runbook induk dulu"}

    return {"type": "change-low", "risk": "low", "needs_issue": True,
            "document_hint": "biasanya tanpa MoP (MoP-lite di action item), lihat ops-rules aturan 9"}


# What the legacy ticket-file flow used to scaffold per type. Kept only for
# start_workflow, which is no longer an MCP tool (retired 2026-10-15: new work starts
# with issue_create); the issue flow decides documents per action item.
_LEGACY_ARTIFACTS = {
    "check": [],
    "incident": ["ticket", "incident_report"],
    "change-low": ["ticket", "mop"],
    "change-high": ["ticket", "mop"],
}


_BANNER_STATUS = re.compile(r"(^>\s*\*\*Status:\*\*\s*)([^·\n]*)", re.MULTILINE)
_BANNER_UPDATED = re.compile(r"^>\s*\*\*Update terakhir:\*\*.*$", re.MULTILINE)


def _append_history_row(content: str, row: str) -> str:
    """Append a row to the ticket's dated history table.

    Handles both shapes: "## Riwayat" (current, see
    docs/standards/ops-issue-format.md) and the legacy "## Status History".
    The row is inserted at the END of that section rather than before a fixed
    following heading, so it keeps working regardless of what comes next — the
    old implementation inserted before a literal "## Related Documents" and
    silently did nothing if that heading was renamed or removed.
    """
    for heading in ("## Riwayat", "## Status History"):
        i = content.find(f"\n{heading}")
        if i == -1:
            continue
        j = content.find("\n## ", i + len(heading) + 1)
        section, tail = (content[i:], "") if j == -1 else (content[i:j], content[j:])
        return content[:i] + section.rstrip("\n") + f"\n{row}\n" + tail
    return content


def update_ticket_status(
    ticket_path: Path,
    new_status: str,
    notes: str,
    related_doc: Optional[tuple[str, str]] = None,
) -> None:
    """Update a ticket's status, refresh its banner, and append a history row.

    Tolerates both ticket shapes on purpose — there are hundreds of tickets in
    the legacy shape across customers, and they must keep working unchanged.
    """
    content = ticket_path.read_text()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if _BANNER_STATUS.search(content):
        # Current shape: rewrite only the status token, so "Bola di" and "Next"
        # on the same line survive. Then refresh "Update terakhir" — this is the
        # step the old implementation lacked, and the reason bodies went stale
        # while claiming "Status: Open" long after a ticket was closed.
        content = _BANNER_STATUS.sub(
            lambda m: f"{m.group(1)}{new_status} ", content, count=1
        )
        content = _BANNER_UPDATED.sub(
            f"> **Update terakhir:** {timestamp} — {notes}", content, count=1
        )
    else:
        # Legacy shape: "**Status**: Open"
        content = re.sub(r"\*\*Status\*\*: \w[\w ]*", f"**Status**: {new_status}", content)

    content = _append_history_row(content, f"| {timestamp} | {new_status} | {notes} |")

    # Documents go in the `Dokumen` row of ## Environment. `## Referensi` was dropped
    # on 2026-09-30 and with it the `| — | — |` placeholder this used to fill, so
    # without this the call would silently do nothing. Legacy tickets still carry the
    # old 2-column table, so that path is kept.
    if related_doc:
        doc_type, doc_path = related_doc
        link = f"[{doc_type}]({doc_path})"
        # `[ \t]*$` not `\s*$`: `\s` matches newlines, so the greedy version swallowed
        # the blank line before the next heading and glued `## Masalah` to the table.
        m = re.search(r"^\|[ \t]*Dokumen[ \t]*\|(?P<val>[^|]*)\|[ \t]*$",
                      content, re.MULTILINE)
        if m:
            cur = m.group("val").strip()
            # Several documents accumulate on one row rather than adding rows, so the
            # Environment table stays short.
            new = f"{cur} · {link}" if cur else link
            content = content[:m.start()] + f"| Dokumen | {new} |" + content[m.end():]
        else:
            # Legacy shape: the 2-column Referensi / Related Documents table.
            content = content.replace("| — | — |", f"| {doc_type} | {doc_path} |", 1)

    ticket_path.write_text(content)


def _scope_prompt(customer: str, slug: str, description: str,
                  scope: Optional[str]) -> Optional[dict]:
    """SoW clauses worth reading, when this customer is gated and scope is still unset.

    Returns None for a customer with no `sow:` in customer.yaml — which is the normal
    case and must stay silent, or the gate would feel like it applies everywhere.
    """
    from msops.tools.scope import has_sow, scope_candidates, IN_SOW, OUT_OF_SOW
    if not has_sow(customer):
        return None
    if scope in (IN_SOW, OUT_OF_SOW):
        return {"decided": scope}
    cand = scope_candidates(customer, f"{slug.replace('-', ' ')} {description}")
    cand["blocking"] = (
        f"{customer} punya SoW, jadi ticket_file_sync_to_issue akan menolak issue tanpa "
        "baris Scope. Putuskan sekarang: scope='in-sow' atau "
        "scope='out-of-sow' + scope_reason='<klausa>'")
    return cand


_DOCS_NOTE = ("{docs} not created: documents are opt-in. Create one with doc_create_mop / "
              "doc_create_incident_report only when an action item needs it (ops-rules rule 9), or "
              "pass with_docs=True.")


def start_workflow(
    root: Path,
    customer: str,
    slug: str,
    description: str,
    dry_run: bool = True,
    env: Optional[str] = None,
    priority: Optional[str] = None,
    scope: Optional[str] = None,
    scope_reason: Optional[str] = None,
    with_docs: bool = False,
) -> dict:
    classification = classify_work(description)
    artifacts = list(_LEGACY_ARTIFACTS.get(classification["type"], []))

    if not artifacts:
        return {"type": "check", "message": "Read-only — no artifacts needed.", "classification": classification}

    # A MoP or incident report is not the default product of a change (ops-rules rule 9). Created
    # together with the ticket they were left as empty scaffolds: nine of them, identical to the
    # line, in one commit on 2026-10-08. Documents are opt-in; otherwise use doc_create_mop /
    # doc_create_incident_report when an action item needs one.
    skipped_docs = [a for a in artifacts if a != "ticket"] if not with_docs else []
    if not with_docs:
        artifacts = [a for a in artifacts if a == "ticket"]

    task_type = classification["type"]

    # Recurrence gate: before proposing new artifacts, surface any prior
    # tickets/MoPs/incidents for this customer that mention the slug. This is
    # what stops a second MoP being drafted for a problem that already has one —
    # the agent sees the existing document's path and reuses it instead.
    needle = slug.replace("-", " ")
    prior = check_recurrence(root, customer, needle)
    recurrence = None
    if prior.get("recurrence"):
        recurrence = {
            "warning": (
                f"{prior['count']} prior artifact(s) for '{customer}' mention "
                f"'{needle}'. Review these before creating new ones — if a MoP "
                f"already covers this change, update it instead of drafting a new one."
            ),
            "matches": prior["matches"],
        }

    if dry_run:
        would_create = []
        if "ticket" in artifacts:
            path, _ = create_ticket(root, customer, slug, dry_run=True,
                                    task_type=task_type, env=env,
                                    priority=priority, scope=scope,
                                    scope_reason=scope_reason)
            would_create.append(str(path))
        if "incident_report" in artifacts:
            path, _ = create_incident_report(root, customer, slug,
                                             severity=priority,
                                             dry_run=True)
            would_create.append(str(path))
        if "mop" in artifacts:
            path, _ = create_mop(root, customer, slug, dry_run=True)
            would_create.append(str(path))
        out = {
            "dry_run": True,
            "classification": classification,
            "would_create": would_create,
            "confirm": "Call start_workflow(..., dry_run=False) to create these files.",
        }
        if skipped_docs:
            out["documents_not_created"] = _DOCS_NOTE.format(docs=", ".join(skipped_docs))
        if recurrence:
            out["recurrence"] = recurrence
        # Put the contract in front of whoever is about to decide, at the only moment
        # they are still deciding. Candidates to read — never a verdict; see
        # msops/tools/scope.py for the measured reason a matcher must not be trusted.
        sc = _scope_prompt(customer, slug, description, scope)
        if sc:
            out["scope"] = sc
        return out

    result = {"classification": classification}
    if skipped_docs:
        result["documents_not_created"] = _DOCS_NOTE.format(docs=", ".join(skipped_docs))
    ticket_path = None

    if "ticket" in artifacts:
        ticket_path = create_ticket(root, customer, slug, task_type=task_type,
                                    env=env, priority=priority, scope=scope,
                                    scope_reason=scope_reason)
        result["ticket_path"] = str(ticket_path)

    if "incident_report" in artifacts:
        # One source for severity: the same value sets the incident report's
        # severity and the ticket's weight, so they cannot disagree. Before
        # this, severity defaulted to P3 here silently while the weight was
        # never recorded at all.
        ir_path = create_incident_report(root, customer, slug,
                                         severity=priority)
        result["incident_report_path"] = str(ir_path)
        if ticket_path:
            update_ticket_status(
                ticket_path, "In Progress", "Incident report created",
                related_doc=("Incident Report", str(ir_path))
            )

    if "mop" in artifacts:
        mop_path = create_mop(root, customer, slug)
        result["mop_path"] = str(mop_path)
        if ticket_path:
            update_ticket_status(
                ticket_path, "Pending Approval", "MoP created — awaiting approval",
                related_doc=("MoP", str(mop_path))
            )

    return result
