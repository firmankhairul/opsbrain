"""Create a basic issue straight on GitHub — the "Get" stage of docs/standards/ops-issue-format.md.

`ticket_file_sync_to_issue` creates an issue from a ticket file and refuses one whose
action-items table is still the placeholder or whose `Bobot kerja` is unfilled. That is
right for a finished ticket and wrong for an issue that has just been reported: the
action items come out of the analysis, and the weight is set by whoever does it. This
creates the issue in the 5-block shape with a placeholder row and `Bobot kerja: TBD`,
and leaves both to the analysis.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from msops.tools.customers import load_customers
from msops.tools.stage import apply as stage_apply, stage_of
from msops.tools.integrations import (
    _ensure_label, _find_issue, _issue_number_from_url, _run, _wire_board, REPO,
)

_ROOT = Path(__file__).resolve().parents[2]
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌]")
_ENVIRONMENTS = ("prod", "non-prod", "unknown")
PLACEHOLDER_ACTION = "Analisa dan usulkan action item"


def _cell(text: str) -> str:
    """One table cell: no pipes, no line breaks."""
    return " ".join(str(text).replace("|", "/").split())


def build_intake_body(customer: str, symptom: str, impact: str, requester: str,
                      environment: str = "unknown", resource: str = "",
                      evidence: str = "", actions: Optional[list[str]] = None,
                      now: Optional[datetime] = None, engagement: str = "") -> str:
    """The issue body: banner, Environment, Masalah, Action items, Catatan & keputusan."""
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    rows = [_cell(a) for a in (actions or []) if a and a.strip()] or [PLACEHOLDER_ACTION]
    env_rows = [("Customer", customer)]
    if engagement.strip():
        env_rows.append(("Engagement", engagement))
    env_rows.append(("Environment", environment))
    if resource.strip():
        env_rows.append(("Resource", resource))
    env_rows.append(("Requester", requester))
    lines = [
        "> **Status:** Open · **Bola di:** Example MSP · **Next:** tentukan owner, lalu analisa",
        f"> **Update terakhir:** {stamp} — issue dibuat",
        "> **Bobot kerja:** TBD (diisi setelah analisa)",
        "",
        "## Environment",
        "",
        "| Item | Value |",
        "|---|---|",
        *[f"| {k} | {_cell(v)} |" for k, v in env_rows],
        "",
        "## Masalah",
        "",
        symptom.strip(),
        "",
        f"**Dampak:** {impact.strip()}",
        "",
        "## Action items",
        "",
        "| # | Action | PIC | Status |",
        "|---|--------|-----|--------|",
        *[f"| {i} | {a} | Example MSP | Pending |" for i, a in enumerate(rows, 1)],
        "",
        "## Catatan & keputusan",
        "",
        evidence.strip() or "Belum ada.",
        "",
    ]
    body = "\n".join(lines)
    # Born in Get: the Tahap line and a Next that names the command, not just "analisa".
    return stage_apply(body, stage_of(body, [], number=None))


def _problems(customer: str, title: str, symptom: str, impact: str, requester: str,
              environment: str, engagement: str = "") -> list[str]:
    out = []
    slug = customer.strip().lower()
    # By folder, via the same loader get_customer uses: customers kept in a git submodule
    # (acme-retail, example-e) have no customer.yaml at <slug>/ itself.
    customers = load_customers(_ROOT)
    known = {c.folder.lower() for c in customers} | {"non-customer"}
    # A folder that holds several unrelated clients (token/, one-off requests) must say which
    # one this issue is for, otherwise the issue cannot be traced back to anybody.
    if any(c.folder.lower() == slug and c.engagements for c in customers) \
            and not engagement.strip():
        out.append(f"{slug} berisi beberapa klien; isi engagement (nama klien permintaan ini)")
    if slug not in known:
        out.append(f"customer {customer!r} tidak dikenal — pakai get_customer untuk slug yang benar")
    for name, val in (("title", title), ("symptom", symptom), ("impact", impact),
                      ("requester", requester)):
        if not val or not val.strip():
            out.append(f"{name} wajib diisi")
    if environment not in _ENVIRONMENTS:
        out.append(f"environment harus salah satu dari {', '.join(_ENVIRONMENTS)}")
    if any(_EMOJI.search(v or "") for v in (title, symptom, impact, requester, engagement)):
        out.append("tanpa emoji di judul atau isi")
    return out


def create_intake_issue(customer: str, title: str, symptom: str, impact: str,
                        requester: str, environment: str = "unknown",
                        resource: str = "", evidence: str = "",
                        actions: Optional[list[str]] = None,
                        dry_run: bool = True, engagement: str = "") -> dict:
    """Create a basic issue on GitHub. Preview unless `dry_run=False`."""
    bad = _problems(customer, title, symptom, impact, requester, environment, engagement)
    if bad:
        return {"error": "issue tidak dibuat — " + " · ".join(bad)}
    slug = customer.strip().lower()
    full_title = f"[{slug}] {title.strip()}"
    label = f"customer:{slug}"
    body = build_intake_body(slug, symptom, impact, requester, environment,
                             resource, evidence, actions, engagement=engagement)
    dup = _find_issue(full_title)
    if dup:
        return {"error": f"issue dengan judul yang sama sudah ada: #{dup['number']} "
                         f"({dup['state'].lower()})", "existing_number": dup["number"]}
    if isinstance(dry_run, str):
        dry_run = dry_run.strip().lower() not in ("false", "0", "no", "f")
    if dry_run:
        return {"dry_run": True, "title": full_title, "label": label, "body": body,
                "confirm": "Panggil lagi dengan dry_run=False untuk membuat issue ini."}
    _ensure_label(label)
    r = _run(["gh", "issue", "create", "--repo", REPO, "--title", full_title,
              "--body", body, "--label", label])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    url = r.stdout.strip()
    number = _issue_number_from_url(url)
    out = {"url": url, "number": number, "title": full_title, "action": "created"}
    if number:
        out.update(_wire_board(slug, number, body, "", "Open"))
        out["tahap"] = "Get (1 dari 4)"
        out["next"] = f"issue_analyze({number}, type, env, actions, login)"
    return out
