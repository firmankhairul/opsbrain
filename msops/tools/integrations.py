"""Sync tickets to GitHub Issues via gh CLI, and to Zoho Desk via REST API."""
from __future__ import annotations
import subprocess
import json
import os
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

REPO = "your-org/ms-ops"

# Ticket Status values that mean the work is finished -> close the issue.
_DONE_STATUSES = ("resolved", "closed", "done")


def _clean_status(raw: str) -> str:
    """Strip markdown emphasis and padding off a parsed Status value.

    Status is compared by equality downstream (`list_tickets`, the open/closed mapping),
    so a stray `*` is not cosmetic — it makes the value match nothing. Safe to strip:
    the vocabulary is Open · In Progress · Pending Approval · Resolved · Escalated ·
    Closed, none of which contain an asterisk.
    """
    return (raw or "").strip().strip("*").strip()


def _extract_ticket_fields(ticket_path: Path) -> dict:
    content = ticket_path.read_text()
    fields = {"title": "", "customer": "", "status": "", "parent": None}

    m = re.search(r'^#\s+(?:Ticket:\s*)?(.+)', content, re.MULTILINE)
    if m:
        fields["title"] = m.group(1).strip()

    m = re.search(r'^customer:\s*(.+)', content, re.MULTILINE)
    if m:
        fields["customer"] = m.group(1).strip()
    else:
        # The customer is the FIRST path segment, not the parent of tickets/.
        # Multi-account customers nest as <customer>/accounts/<account>/tickets/,
        # where the parent is the account name — labelling by that would scatter
        # one customer's issues across several labels.
        parts = ticket_path.parts
        for i, p in enumerate(parts):
            if p != "tickets" or i == 0:
                continue
            if i >= 3 and parts[i - 2] == "accounts":
                fields["customer"] = parts[i - 3]   # <customer>/accounts/<acct>/tickets/
            else:
                fields["customer"] = parts[i - 1]   # <customer>/tickets/
            break

    # Status. Current shape carries it on the banner line
    #   "> **Status:** Open · **Bola di:** Example MSP · **Next:** …"
    # legacy tickets carry a bare "**Status**: Open". Try the banner first and cut
    # at the "·" separator, otherwise "Bola di"/"Next" would leak into the status
    # and the open/closed mapping below would never match.
    m = re.search(r'^\s*>\s*\*\*status:?\*\*:?\s*(.+)', content,
                  re.MULTILINE | re.IGNORECASE)
    if m:
        fields["status"] = m.group(1).split("·")[0].strip()
    else:
        # `:\*{0,2}` matters: the shape `**Status:** Resolved` puts the colon INSIDE
        # the bold, so a pattern that stops at the colon leaves `**` in the value. That
        # made 5 real tickets parse as `'** Resolved'`, and since list_tickets filters on
        # exact equality the ticket vanished from every status listing with no error.
        m = re.search(r'^\*{0,2}status\*{0,2}\s*:\*{0,2}\s*(.+)', content,
                      re.MULTILINE | re.IGNORECASE)
        if m:
            fields["status"] = _clean_status(m.group(1))
        else:
            # Fallback: a few older tickets have a history table but no status
            # line at all. Take the status cell of the LAST dated row, otherwise
            # they parse as "" and the issue is kept open even when the ticket's
            # own history ends in Resolved. Mirrors docs._read_status.
            rows = re.findall(r'^\|\s*20\d\d-\d\d-\d\d[^|]*\|\s*([^|]+?)\s*\|',
                              content, re.MULTILINE)
            if rows:
                # The cell's own value can be bold — acme-retail's history row reads
                # `| … | **Closed** | … |` — so it needs the same normalisation.
                fields["status"] = _clean_status(rows[-1])

    # Umbrella / parent issue, from a `**Parent**: #79` meta line. Optional —
    # only batch work has an umbrella. Kept as an explicit line rather than
    # inferred from `## Referensi` prose, because prose is not parseable
    # reliably: the same line may name several issues and there is no way to
    # tell which one is the parent.
    #
    # Accepted at the start of a line or after a `·`/`|` separator, because the
    # meta fields sit together on one line (`**ID**: … · **Customer**: …`).
    # The colon must follow "parent" directly, so prose like "Parent process:"
    # does not match.
    m = re.search(r'(?:^|[·|]\s*)\*{0,2}parent\*{0,2}\s*:\s*#?(\d+)', content,
                  re.MULTILINE | re.IGNORECASE)
    if m:
        fields["parent"] = int(m.group(1))

    # Body is the FULL ticket, not just the "## Issue" section, so the issue
    # mirrors the ticket. The first H1 becomes the issue title, so drop it.
    body = re.sub(r'^#\s+.*\n', '', content, count=1)
    fields["body"] = body.strip()

    return fields


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kw)


def _issue_number_from_url(url: str) -> int | None:
    """Trailing issue number from a `gh issue create` URL."""
    m = re.search(r'/(\d+)\s*$', url.strip())
    return int(m.group(1)) if m else None


def _link_sub_issue(parent: int, child: int) -> dict:
    """Register `child` as a native sub-issue of `parent`.

    GitHub's parent/child relation is a real relation, not a mention — writing
    "Sub-issue of #79" in the body does not create it, and the issue will not
    appear in the umbrella's sub-issue list or progress count.

    The endpoint takes the child's **database id** (`.id`, e.g. 5639751817), not
    its number. Passing the number targets an unrelated issue or 404s, which is
    why the id is looked up first.
    """
    r = _run(["gh", "api", f"repos/{REPO}/issues/{child}", "--jq", ".id"])
    if r.returncode != 0:
        return {"linked": False, "error": r.stderr.strip() or "db id lookup failed"}
    dbid = r.stdout.strip()
    if not dbid.isdigit():
        return {"linked": False, "error": f"unexpected db id: {dbid!r}"}

    r = _run(["gh", "api", "--method", "POST",
              f"repos/{REPO}/issues/{parent}/sub_issues",
              "-F", f"sub_issue_id={dbid}"])
    if r.returncode == 0:
        return {"linked": True, "parent": parent}
    err = (r.stderr or "").strip()
    # Re-syncing an already-linked ticket must not fail the whole sync.
    if "already" in err.lower():
        return {"linked": True, "parent": parent, "already_linked": True}
    return {"linked": False, "error": err}


def _find_issue(title: str) -> dict | None:
    """Return {number, state} for an existing issue with an exact title match."""
    r = _run(["gh", "issue", "list", "--repo", REPO, "--state", "all",
              "--search", f'in:title "{title}"',
              "--json", "number,title,state", "--limit", "50"])
    if r.returncode != 0:
        return None
    try:
        for it in json.loads(r.stdout or "[]"):
            if it.get("title") == title:
                return {"number": it["number"], "state": it.get("state", "")}
    except json.JSONDecodeError:
        return None
    return None


# Label colour and description, by label. `--force` below means this OVERWRITES an
# existing label's colour, which is why every `customer:*` label in the repo is the same
# green -- they have all passed through here. Only `scope:out-of-sow` is singled out: it
# is the one label a PM should spot without reading, and born the same green as every
# customer label it was invisible on the board.
_LABEL_STYLE = {
    "scope:out-of-sow": ("d73a4a", "Aktivitas di luar Scope of Work customer — "
                                   "klausanya disebut di baris Scope pada body issue"),
    "scope:in-sow":     ("0e8a16", "Aktivitas di dalam Scope of Work customer"),
}
_LABEL_DEFAULT = ("0e8a16", "")


def _ensure_label(label: str) -> None:
    """Create the label, or update its colour and description if it already exists.

    `--force` makes this an upsert, not a create-if-missing: the colour is reasserted on
    every sync. That is deliberate for the scope labels, whose whole job is to be read at
    a glance.
    """
    colour, desc = _LABEL_STYLE.get(label, _LABEL_DEFAULT)
    cmd = ["gh", "label", "create", label, "--repo", REPO, "--color", colour, "--force"]
    if desc:
        cmd += ["--description", desc]
    _run(cmd)


def get_issue(number: int, include_history: bool = True, comment_limit: int = 3) -> dict:
    """Fetch a GitHub Issue's live data by number, straight from GitHub via `gh` CLI.

    No local ticket file is read — this is the read counterpart to
    ticket_file_sync_to_issue (which only pushes local -> GitHub). Use it to check
    an issue's actual current state/body/comments on GitHub.
    """
    if comment_limit < 0:
        return {"error": "comment_limit must be non-negative"}
    r = _run(["gh", "issue", "view", str(number), "--repo", REPO,
              "--json", "number,title,state,body,labels,url,createdAt,updatedAt,comments,assignees"])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    try:
        issue = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": f"Could not parse gh output: {r.stdout[:300]}"}
    if not include_history:
        comments = issue.get("comments") or []
        issue["comment_count"] = len(comments)
        issue["comments_omitted"] = max(0, len(comments) - comment_limit)
        issue["comments"] = [
            {"url": c.get("url"), "createdAt": c.get("createdAt"),
             "author": c.get("author"), "body": (c.get("body") or "")[:2000],
             "body_truncated": len(c.get("body") or "") > 2000}
            for c in (comments[-comment_limit:] if comment_limit else [])
        ]
    return issue


def find_issue_by_title(title_query: str) -> list[dict]:
    """Search GitHub Issues by title, straight from GitHub via `gh` CLI (no local read)."""
    r = _run(["gh", "issue", "list", "--repo", REPO, "--state", "all",
              "--search", f'in:title "{title_query}"',
              "--json", "number,title,state,url", "--limit", "50"])
    if r.returncode != 0:
        return [{"error": r.stderr.strip()}]
    try:
        return json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return [{"error": f"Could not parse gh output: {r.stdout[:300]}"}]


# The 5 blocks that belong in an issue body (docs/standards/ops-issue-format.md).
# `## Riwayat` is deliberately absent: the ticket file needs it because
# update_ticket_status appends there, the issue body must not have it because it
# duplicates the banner. That asymmetry is exactly why sync stopped pushing verbatim.
_ISSUE_BLOCKS = ("environment", "masalah", "action items",
                 "root cause", "catatan & keputusan", "catatan")


# A markdown link whose target is a repo-relative path: no scheme, no leading slash, no
# anchor. Those render as dead links in an ISSUE body — GitHub only resolves them inside
# files in the repo. The ticket is full of them because there they are correct.
_REL_LINK = re.compile(r"\]\((?!https?://|/|#)([^)\s]+)\)")


def _absolutise(text: str) -> str:
    """Turn repo-relative markdown links into blob URLs.

    The ticket file legitimately uses relative paths — they work in a file in the repo.
    An issue body does not resolve them, so copying them across produces links that look
    right and go nowhere. Found while creating the first test issue: the `Dokumen` row
    carried `[MoP](acme-retail/mop/...)` straight into the body.
    """
    return _REL_LINK.sub(
        lambda m: f"](https://github.com/{REPO}/blob/main/{m.group(1)})", text)


def derive_issue_body(ticket_text: str, ticket_rel: str | None = None) -> dict:
    """Reduce a ticket file to the 5-block issue body.

    The ticket is the working document and may be long; the issue body must answer the
    five PM questions on its own and nothing more. Nothing is lost by dropping a section
    here — the ticket file keeps everything, and the body links to it through the
    `Dokumen` row.

    Returns {"body", "kept", "dropped", "verbatim"}. `verbatim` is True when the ticket
    has no recognisable shape at all: reducing a legacy ticket to an empty shell would be
    worse than a long body, so it is passed through and the caller is told.
    """
    lines = ticket_text.splitlines()
    head: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    cur: tuple[str, list[str]] | None = None
    for l in lines:
        m = re.match(r"^#{2,3}\s+(.+?)\s*$", l)
        if m:
            if cur:
                sections.append(cur)
            cur = (m.group(1).strip(), [l])
            continue
        (cur[1] if cur else head).append(l)
    if cur:
        sections.append(cur)

    # Derive ONLY from a ticket that is actually in the 5-block shape. The two
    # load-bearing parts are the banner (answers "where does it stand / whose ball /
    # next / when") and the action-items table (the progress map with its PIC). Without
    # both, dropping the other sections leaves a near-empty shell — the acme-retail ticket
    # kept only `## Root Cause` and would have produced a body that says nothing. A long
    # legacy body is worse than nothing; an empty one is worse than both.
    has_banner = any(re.match(r"^>\s*\*\*Status:\*\*", l) for l in head)
    has_actions = any(n.lower().startswith("action items") for n, _ in sections)
    if not (has_banner and has_actions):
        return {"body": ticket_text.strip(), "kept": [], "dropped": [],
                "verbatim": True,
                "reason": ("ticket belum bentuk 5 blok — "
                           + ("tidak ada banner; " if not has_banner else "")
                           + ("tidak ada ## Action items" if not has_actions else "")).strip("; ")}

    out = list(head)
    kept, dropped = [], []
    for name, body in sections:
        if any(name.lower().startswith(b) for b in _ISSUE_BLOCKS):
            kept.append(name)
            out.extend(body)
            # The body is a summary; the ticket is where the detail lives, so the link
            # has to be in the body or the detail is unreachable from the issue.
            if name.lower().startswith("environment") and ticket_rel:
                # Append the ticket to a Dokumen row that already lists other
                # documents, instead of skipping it entirely.
                for k in range(len(out) - 1, -1, -1):
                    if "Dokumen" in out[k] and out[k].strip().startswith("|"):
                        url = f"https://github.com/{REPO}/blob/main/{ticket_rel}"
                        cells = out[k].strip().strip("|").split("|")
                        cur = cells[1].strip() if len(cells) > 1 else ""
                        val = f"{cur} · [ticket]({url})" if cur else f"[ticket]({url})"
                        out[k] = f"| Dokumen | {val} |"
                        break
                else:
                    pass
                if not any("Dokumen" in x for x in body):
                    for k in range(len(out) - 1, -1, -1):
                        if out[k].strip().startswith("|"):
                            # A full blob URL, not a repo-relative path: an ISSUE body
                            # does not resolve relative repo links the way a markdown
                            # file in the repo does, so `../acme-retail/...` would render
                            # as a dead link. The whole point is that it is clickable.
                            url = f"https://github.com/{REPO}/blob/main/{ticket_rel}"
                            out.insert(k + 1, f"| Dokumen | [ticket]({url}) |")
                            break
        else:
            dropped.append(name)

    text = "\n".join(out).rstrip() + "\n"
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _absolutise(text)
    return {"body": text, "kept": kept, "dropped": dropped, "verbatim": False}


_PLACEHOLDER_ROW = re.compile(r"^\|\s*\d+\s*\|\s*\|", re.MULTILINE)
_WEIGHT_NUM_RE = re.compile(r"\*\*Bobot kerja:?\*\*\s*(\d+)", re.IGNORECASE)


def _scope_of(body: str):
    from msops.tools.scope import parse_scope
    return parse_scope(body)


def _creation_blockers(body: str, customer: str | None = None) -> list[str]:
    """What must be filled in before an issue is worth creating.

    Only the things a scaffold cannot supply and a reader cannot do without. Not a
    style check — `issue_audit_format` covers the rest after the fact.

    The scope check applies ONLY to a customer whose customer.yaml names a `sow:`.
    Of 47 customers that is however many were deliberately switched on, so this
    blocks nothing for anyone else. It is a gate rather than a nudge for the same
    reason the weight is: `Bobot kerja` was documented long before it was enforced
    and reached 7% of issues; enforced at creation it reached 93% in a month.
    """
    out = []
    if _PLACEHOLDER_ROW.search(body):
        out.append("tabel Action items masih baris placeholder kosong "
                   "(body tidak bisa menjawab 'bola di siapa')")
    if not _WEIGHT_NUM_RE.search(body):
        # An incident needs priority= on top of env=, so name the one that is actually
        # missing instead of sending the caller to the wrong parameter.
        need = ("`priority=` (P1..P4) dan `env=`" if "insiden P1=" in body
                else "`env=` (prod/non-prod)")
        out.append(f"`Bobot kerja` belum terisi — akan hilang dari total capacity "
                   f"tanpa peringatan; tentukan {need}, lalu isi barisnya di berkas "
                   f"tiket dari tabel docs/standards/ops-issue-format.md")
    if customer:
        from msops.tools.scope import has_sow, parse_scope
        if has_sow(customer):
            _, _, st = parse_scope(body)
            if st in ("absent", "undecided"):
                out.append(
                    f"`Scope` belum diputuskan — {customer} punya SoW, jadi tiap "
                    "issue harus menyatakan dalam/di luar SoW. Panggil "
                    "scope_candidates() untuk melihat klausanya, lalu tulis "
                    "baris `Scope` di berkas tiket")
            elif st == "no-reason":
                out.append(
                    "`Scope` di luar SoW tapi klausanya tidak disebut — tanpa itu "
                    "daftarnya tidak bisa dipakai sales; isi scope_reason=")
            elif st == "unparseable":
                out.append("baris `Scope` tidak terbaca — pakai `dalam SoW` atau "
                           "`di luar SoW — <klausa>`")
    return out


# Ticket vocabulary -> board Status options. The two differ on purpose: a ticket has
# six states, the board four columns. Open/Resolved/Closed/Escalated have no column of
# their own, so they are mapped rather than guessed at call time.
_BOARD_STATUS = {
    "open": "Todo",
    "todo": "Todo",
    "in progress": "In Progress",
    "pending approval": "Pending Approval",
    # Escalated means waiting on someone else — the board's waiting column.
    "escalated": "Pending Approval",
    "resolved": "Done",
    "closed": "Done",
    "done": "Done",
    "selesai": "Done",
}

# classify_work's task type -> board Segment. `Project` and `Monthly Report` are not
# derivable from a task type, so they are left for a human instead of guessed.
_BOARD_SEGMENT = {
    "incident": "Incident",
    "change-low": "Change",
    "change-high": "Change",
    "check": "BAU",
}


def _board_status(ticket_status: str) -> str | None:
    """Board column for a ticket Status, or None when there is no honest mapping.

    Matched on the first word so a real banner like
    `Resolved (2026-09-07) — pending handover` still resolves.
    """
    first = (ticket_status or "").strip().lower().strip("*_`")
    if not first:
        return None
    for key in _BOARD_STATUS:
        if first == key or first.startswith(key + " ") or first.startswith(key + "("):
            return _BOARD_STATUS[key]
    return _BOARD_STATUS.get(first.split()[0] if first.split() else "")


def _board_segment(task_type: str) -> str | None:
    return _BOARD_SEGMENT.get((task_type or "").strip().lower())


def _wire_board(customer: str, number: int, body: str, task_type: str,
                ticket_status: str) -> dict:
    """Set the board fields a new issue can be born with.

    Called only on CREATE. Weight is the one that matters: GitHub Projects Insights
    charts from the BOARD, so an issue whose weight lives only in markdown is invisible
    there — the gap that reached 11 issues worth 98 on acme-retail before anyone noticed.
    Status and Segment come along because they are derivable and an empty Segment makes
    the board ungroupable.

    Never raises and never fails the caller: the issue is the deliverable, the board is
    its mirror, and losing a field value must not lose the issue. Returns
    {"board_error": ...} instead.
    """
    from msops.tools.board import board_number, set_board_fields
    if board_number(customer) is None:
        return {}
    fields: dict = {}
    m = _WEIGHT_NUM_RE.search(body or "")
    if m:
        fields["weight"] = int(m.group(1))
    st = _board_status(ticket_status)
    if st:
        fields["status"] = st
    seg = _board_segment(task_type)
    if seg:
        fields["segment"] = seg
    if not fields:
        return {}
    try:
        r = set_board_fields(customer, number, dry_run=False, **fields)
    except Exception as e:  # noqa: BLE001 - the board must never break issue creation
        return {"board_error": f"{type(e).__name__}: {e}"}
    if r.get("ok"):
        return {"board_set": fields}
    return {"board_error": r.get("error") or r.get("results"), "board_attempted": fields}


def _derive_for(ticket_path: Path, fields: dict) -> dict:
    """derive_issue_body for this ticket, with the repo-relative path for the link."""
    try:
        rel = str(ticket_path.resolve().relative_to(Path(__file__).resolve().parents[2]))
    except ValueError:
        rel = None
    return derive_issue_body(fields["body"], rel)


def sync_ticket_to_github(ticket_path: Path, dry_run: bool = True,
                          force: bool = False) -> dict:
    """Create or update a GitHub Issue from a ticket (idempotent).

    - **Does NOT own the body of an existing issue.** On update it syncs state
      (open/close), the label and the parent relation, and leaves the body alone.
      Decided 2026-09-30: the ticket file needs `## Riwayat` (update_ticket_status
      appends there) while the issue body must not have it, so the two cannot share
      one shape. #316 proved it — ticket and body were byte-identical, so tidying the
      body and re-syncing would silently put Riwayat back. The issue body is
      canonical; issue_update_action_item and issue_rewrite_body maintain it.
    - On CREATE the body is derived from the ticket — the 5 blocks only, no
      `## Riwayat`, no investigation prose — with a `Dokumen` row linking the ticket.
    - Auto-creates the customer label if missing.
    - Updates an existing issue with the same title instead of duplicating.
    - **Does NOT own the state of an existing issue either.** The ticket Status only
      sets open/closed when the issue is CREATED. On update a disagreement is reported
      as `state_mismatch` and nothing is changed — the old behaviour reopened a closed
      issue whenever its ticket still said "In Progress", which on 2026-10-01 applied
      to 12 correctly closed issues. Closing is now `issue_update_action_item`'s proposal
      (all items ✅) with a human approving.
    - Returns the issue `number` on every path, so the caller can set project
      board fields without searching for the issue it just created.
    - If the ticket carries a `**Parent**: #79` line, registers the issue as a
      native sub-issue of that umbrella. This is a real GitHub relation —
      mentioning the umbrella in prose does not create it, and the issue would
      not show up in the umbrella's sub-issue list.
    """
    if not ticket_path.exists():
        return {"error": f"Ticket not found: {ticket_path}"}

    fields = _extract_ticket_fields(ticket_path)
    title = f"[{fields['customer']}] {fields['title']}"
    label = f"customer:{fields['customer'].lower()}"
    # A second label when the ticket records a scope verdict. Two labels, never one:
    # with only `scope:out-of-sow`, an unlabelled issue cannot be told apart from one
    # nobody has looked at yet — and at the start that is nearly all of them.
    _sv, _, _sst = _scope_of(fields["body"])
    labels = [label] + ([f"scope:{_sv}"] if _sst == "ok" else [])
    status = fields["status"].lower()
    should_close = any(status.startswith(s) for s in _DONE_STATUSES)
    desired_state = "closed" if should_close else "open"

    existing = _find_issue(title)
    action = "update" if existing else "create"

    if dry_run:
        return {
            "dry_run": True,
            "action": action,
            "existing_number": existing["number"] if existing else None,
            "title": title,
            "label": label,
            "labels": labels,
            "ticket_status": fields["status"],
            "desired_state": desired_state,
            "parent": fields.get("parent"),
            "body_chars": len(fields["body"]),
            "body_preview": fields["body"][:300],
            **({"body_untouched": "issue sudah ada — body tidak disentuh",
                "state_untouched": "state issue tidak disentuh",
                **({"state_mismatch":
                    f"ticket bilang {fields['status']!r} (-> {desired_state}), "
                    f"issue {existing.get('state','').lower()} — tidak diubah"}
                   if should_close != (existing.get("state", "").lower() == "closed")
                   else {})}
               if existing else
               {"derived": {k: v for k, v in
                            _derive_for(ticket_path, fields).items() if k != "body"},
                "derived_preview": _derive_for(ticket_path, fields)["body"][:400],
                "creation_blockers":
                    _creation_blockers(_derive_for(ticket_path, fields)["body"],
                                       fields["customer"])}),
        }

    for lb in labels:
        _ensure_label(lb)

    if existing:
        num = str(existing["number"])
        # No --body: the issue body is canonical and is not ours to overwrite.
        r = _run(["gh", "issue", "edit", num, "--repo", REPO,
                  "--add-label", ",".join(labels)])
        if r.returncode != 0:
            return {"error": r.stderr.strip()}
        # State is NOT ours either, for the same reason the body is not: the ticket
        # file is a document and goes stale, while the issue is the live record. The
        # old behaviour reopened a closed issue whenever the ticket still said
        # "In Progress" — measured 2026-10-01, that would have reopened 12 correctly
        # closed issues, among them #239/#240/#241/#242 (Windows upgrades that were
        # finished and whose tickets were simply never updated).
        #
        # Reported instead of acted on: a mismatch is useful information — it means the
        # ticket file needs attention — and silently discarding it would hide that.
        cur = existing.get("state", "").lower()
        url = _run(["gh", "issue", "view", num, "--repo", REPO,
                    "--json", "url", "-q", ".url"]).stdout.strip()
        out = {"url": url, "number": existing["number"], "title": title,
               "action": "updated", "state": cur,
               "body_untouched": True, "state_untouched": True}
        if should_close != (cur == "closed"):
            out["state_mismatch"] = (
                f"ticket bilang {fields['status']!r} (-> {desired_state}), issue {cur} "
                "— TIDAK diubah. Perbarui ticket, atau tutup/buka issue-nya sendiri.")
        if fields.get("parent"):
            out["sub_issue"] = _link_sub_issue(fields["parent"], existing["number"])
        return out

    derived = _derive_for(ticket_path, fields)
    # Gate at creation, not after. An issue born with an empty action-items row cannot
    # answer "whose ball" — one of the five questions the body exists to answer — and an
    # unfilled `Bobot kerja` disappears from capacity totals with no warning. Catching
    # it here is the difference between a rule and a documented wish: `## Referensi` was
    # mandated by the standard and was the first thing to rot.
    gate = [] if force else _creation_blockers(derived["body"], fields["customer"])
    if gate:
        return {"error": "issue tidak dibuat — " + " · ".join(gate),
                "hint": "lengkapi ticket-nya dulu, atau panggil dengan force=True",
                "title": title, "action": "blocked"}
    r = _run(["gh", "issue", "create", "--repo", REPO,
              "--title", title, "--body", derived["body"],
              "--label", ",".join(labels)])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    url = r.stdout.strip()
    # Callers need the number to set board fields or link the issue; without it
    # they have to search for the issue they just created.
    number = _issue_number_from_url(url)
    if should_close and number:
        # rare: ticket already resolved at first sync
        _run(["gh", "issue", "close", str(number), "--repo", REPO])
    out = {"url": url, "number": number, "title": title,
           "action": "created", "state": desired_state,
           "derived_kept": derived["kept"], "derived_dropped": derived["dropped"]}
    if number:
        out.update(_wire_board(fields["customer"], number, derived["body"],
                               _extract_task_type(ticket_path.read_text()),
                               fields["status"]))
    if derived["verbatim"]:
        out["warning"] = ("ticket tidak punya bentuk 5 blok — body dikirim verbatim. "
                          "Rapikan ticket-nya, atau body issue lewat issue_rewrite_body.")
    if fields.get("parent") and number:
        out["sub_issue"] = _link_sub_issue(fields["parent"], number)
    return out


# ---------------------------------------------------------------------------
# Zoho Desk integration
# ---------------------------------------------------------------------------
# Credentials are read from environment variables (never hardcoded):
#   ZOHO_CLIENT_ID       — from api-console.zoho.com
#   ZOHO_CLIENT_SECRET   — from api-console.zoho.com
#   ZOHO_REFRESH_TOKEN   — generated once during OAuth setup
#   ZOHO_DESK_ORG_ID     — Zoho Desk Organization ID (found in Setup → General)
#   ZOHO_DESK_DEPT_ID    — Department ID to file tickets under (optional)
#
# Token refresh is handled automatically — access tokens expire in 1 hour,
# the refresh token is permanent until revoked.
# ---------------------------------------------------------------------------

# Map ms-ops task types → Zoho Desk ticket type and priority
_ZOHO_TYPE_MAP = {
    "incident":    ("Incident",        "High"),
    "change-high": ("Change Request",  "High"),
    "change-low":  ("Service Request", "Normal"),
    "check":       ("Service Request", "Low"),
}

# ms-ops Status → Zoho Desk Status
_ZOHO_STATUS_MAP = {
    "open":             "Open",
    "in progress":      "In Progress",
    "pending approval": "On Hold",
    "resolved":         "Resolved",
    "closed":           "Closed",
    "escalated":        "Escalated",
}

_ZOHO_TOKEN_CACHE: dict = {}   # {"access_token": ..., "expires_at": ...}


def _zoho_env() -> dict:
    """Return Zoho credentials from env. Raise if any required var is missing."""
    keys = ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN", "ZOHO_DESK_ORG_ID")
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(
            f"Missing Zoho env vars: {', '.join(missing)}. "
            "Set them in your shell or a .env file. "
            "See: https://api-console.zoho.com"
        )
    return {k: os.environ[k] for k in keys}


def _zoho_access_token(env: dict) -> str:
    """Return a valid Zoho OAuth access token, refreshing if expired."""
    global _ZOHO_TOKEN_CACHE

    now = time.time()
    if _ZOHO_TOKEN_CACHE.get("access_token") and now < _ZOHO_TOKEN_CACHE.get("expires_at", 0) - 60:
        return _ZOHO_TOKEN_CACHE["access_token"]

    data = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "client_id":     env["ZOHO_CLIENT_ID"],
        "client_secret": env["ZOHO_CLIENT_SECRET"],
        "refresh_token": env["ZOHO_REFRESH_TOKEN"],
    }).encode()

    req = urllib.request.Request(
        "https://accounts.zoho.com/oauth/v2/token",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Zoho token refresh failed: {exc.code} {exc.read().decode()}") from exc

    if "access_token" not in body:
        raise RuntimeError(f"Zoho token refresh error: {body}")

    _ZOHO_TOKEN_CACHE = {
        "access_token": body["access_token"],
        "expires_at":   now + int(body.get("expires_in", 3600)),
    }
    return _ZOHO_TOKEN_CACHE["access_token"]


def _zoho_request(method: str, path: str, payload: dict | None = None) -> dict:
    """Make an authenticated Zoho Desk API call. Returns parsed JSON."""
    env = _zoho_env()
    token = _zoho_access_token(env)
    org_id = env["ZOHO_DESK_ORG_ID"]

    url = f"https://desk.zoho.com/api/v1{path}"
    body = json.dumps(payload).encode() if payload else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization",  f"Zoho-oauthtoken {token}")
    req.add_header("orgId",          org_id)
    req.add_header("Content-Type",   "application/json")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode()
        raise RuntimeError(f"Zoho Desk API {method} {path} → {exc.code}: {err_body}") from exc


def _zoho_find_ticket(subject: str) -> dict | None:
    """Search Zoho Desk for an existing open/on-hold ticket with exact subject."""
    try:
        result = _zoho_request("GET", f"/tickets?subject={urllib.parse.quote(subject)}&limit=5")
        for ticket in result.get("data", []):
            if ticket.get("subject") == subject:
                return {"id": ticket["id"], "ticketNumber": ticket.get("ticketNumber"), "status": ticket.get("status")}
    except Exception:
        pass
    return None


def _extract_task_type(ticket_content: str) -> str:
    """Infer ms-ops task type from ticket content for Zoho type/priority mapping."""
    content_lower = ticket_content.lower()
    if any(w in content_lower for w in ("incident", "outage", "down", "error", "gagal", "offline")):
        return "incident"
    if any(w in content_lower for w in ("migrate", "upgrade", "terraform", "major", "cluster")):
        return "change-high"
    return "change-low"


def sync_ticket_to_zoho(ticket_path: Path, dry_run: bool = True) -> dict:
    """Create or update a Zoho Desk ticket from a local ms-ops ticket file.

    Behaviour:
    - Reads ticket markdown, extracts subject/customer/status/description.
    - Maps ms-ops Status → Zoho Desk Status.
    - Maps task type (incident / change-high / change-low) → Zoho Type + Priority.
    - Subject format: "[customer] <ticket title>" — same as GitHub sync.
    - Idempotent: searches for existing ticket by subject before creating.
    - dry_run=True (default): preview only, no API call made.
    - dry_run=False: create or update ticket in Zoho Desk.

    Required env vars: ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN,
    ZOHO_DESK_ORG_ID. Optional: ZOHO_DESK_DEPT_ID.
    """
    if not ticket_path.exists():
        return {"error": f"Ticket not found: {ticket_path}"}

    # Reuse same field extractor as GitHub sync
    fields = _extract_ticket_fields(ticket_path)
    subject = f"[{fields['customer']}] {fields['title']}"
    status_raw = fields["status"].lower().strip()
    zoho_status = _ZOHO_STATUS_MAP.get(status_raw, "Open")

    task_type = _extract_task_type(ticket_path.read_text())
    zoho_type, zoho_priority = _ZOHO_TYPE_MAP.get(task_type, ("Service Request", "Normal"))

    dept_id = os.environ.get("ZOHO_DESK_DEPT_ID")

    # Default contact: engineer@example-msp.com (internal ms-ops tickets)
    default_contact_id = os.environ.get("ZOHO_DESK_CONTACT_ID", "")

    payload: dict = {
        "subject":     subject,
        "description": fields["body"][:10000],
        "status":      zoho_status,
        "priority":    zoho_priority,
        "contactId":   default_contact_id,
    }
    if dept_id:
        payload["departmentId"] = dept_id

    if dry_run:
        existing = None
        try:
            existing = _zoho_find_ticket(subject)
        except EnvironmentError as exc:
            return {"dry_run": True, "warning": str(exc), "subject": subject,
                    "zoho_status": zoho_status, "zoho_type": zoho_type,
                    "zoho_priority": zoho_priority, "action": "would_create"}

        return {
            "dry_run":       True,
            "action":        "update" if existing else "create",
            "subject":       subject,
            "zoho_status":   zoho_status,
            "zoho_type":     zoho_type,
            "zoho_priority": zoho_priority,
            "existing":      existing,
            "payload_preview": {k: v for k, v in payload.items() if k != "description"},
        }

    # --- live run ---
    existing = _zoho_find_ticket(subject)

    if existing:
        ticket_id = existing["id"]
        _zoho_request("PATCH", f"/tickets/{ticket_id}", payload)
        return {
            "action":        "updated",
            "ticket_id":     ticket_id,
            "ticket_number": existing.get("ticketNumber"),
            "subject":       subject,
            "zoho_status":   zoho_status,
            "url":           f"https://desk.zoho.com/agent/example-msp/tickets/{ticket_id}",
        }

    result = _zoho_request("POST", "/tickets", payload)
    ticket_id = result.get("id")
    return {
        "action":        "created",
        "ticket_id":     ticket_id,
        "ticket_number": result.get("ticketNumber"),
        "subject":       subject,
        "zoho_status":   zoho_status,
        "url":           f"https://desk.zoho.com/agent/example-msp/tickets/{ticket_id}",
    }


def _fmt_zoho_ticket(t: dict) -> dict:
    """Extract relevant fields from a raw Zoho Desk ticket object."""
    ticket_id = t.get("id", "")
    return {
        "id":           ticket_id,
        "number":       t.get("ticketNumber", ""),
        "subject":      t.get("subject", ""),
        "status":       t.get("status", ""),
        "priority":     t.get("priority", ""),
        "type":         t.get("ticketType", ""),
        "created_at":   t.get("createdTime", ""),
        "modified_at":  t.get("modifiedTime", ""),
        "assignee":     (t.get("assignee") or {}).get("firstName", "") + " " +
                        (t.get("assignee") or {}).get("lastName", ""),
        "contact":      (t.get("contact") or {}).get("email", ""),
        "department":   (t.get("department") or {}).get("name", ""),
        "url":          f"https://desk.zoho.com/agent/example-msp/tickets/{ticket_id}",
    }


def list_zoho_tickets(
    status: str | None = None,
    limit: int = 25,
    dept_id: str | None = None,
    sort_by: str = "createdTime",
    sort_order: str = "desc",
) -> list[dict]:
    """List tickets from Zoho Desk with optional filters.

    Args:
        status:     Filter by status. One of: Open, In Progress, On Hold,
                    Resolved, Closed, Escalated. None = all statuses.
        limit:      Max tickets to return (1–50). Default 25.
        dept_id:    Filter by department ID. None = use ZOHO_DESK_DEPT_ID env,
                    or all departments if that is also unset.
        sort_by:    Field to sort by. Default "createdTime".
        sort_order: "asc" or "desc". Default "desc" (newest first).

    Returns a list of dicts with key ticket fields.
    Raises RuntimeError if the API call fails.
    """
    limit = max(1, min(limit, 50))
    params: dict[str, str] = {
        "limit":     str(limit),
        "sortBy":    sort_by,
        # Zoho Desk API v1 does not accept an "order" query param — omitted.
    }
    if status:
        params["status"] = status
    resolved_dept = dept_id or os.environ.get("ZOHO_DESK_DEPT_ID")
    if resolved_dept:
        params["departmentId"] = resolved_dept

    qs = urllib.parse.urlencode(params)
    result = _zoho_request("GET", f"/tickets?{qs}")
    tickets = result.get("data", [])
    return [_fmt_zoho_ticket(t) for t in tickets]


def get_zoho_ticket(ticket_id: str) -> dict:
    """Fetch full details of a single Zoho Desk ticket by its ID.

    Also fetches the first page of comments (threads) and attaches them
    under the "comments" key, so the caller can see the full conversation.

    Args:
        ticket_id: Zoho Desk ticket ID (numeric string from list_zoho_tickets).

    Returns a dict with ticket fields + "description" + "comments".
    """
    # Fetch ticket detail
    ticket = _zoho_request("GET", f"/tickets/{ticket_id}")
    result = _fmt_zoho_ticket(ticket)
    result["description"] = ticket.get("description", "")

    # Fetch comments / thread
    try:
        threads = _zoho_request("GET", f"/tickets/{ticket_id}/comments?limit=20")
        result["comments"] = [
            {
                "author":  c.get("author", {}).get("name", ""),
                "content": c.get("content", ""),
                "time":    c.get("createdTime", ""),
                "type":    c.get("type", ""),
            }
            for c in threads.get("data", [])
        ]
    except Exception:
        result["comments"] = []

    return result


def close_zoho_ticket(ticket_id: str, reason: str = "") -> dict:
    """Close a Zoho Desk ticket by setting its status to Closed.

    Args:
        ticket_id: Zoho Desk ticket ID (numeric string).
        reason:    Optional closing note added as a comment before closing.

    Returns dict with ticket_id, ticket_number, and final status.
    """
    # Add closing comment if reason provided
    if reason:
        try:
            _zoho_request("POST", f"/tickets/{ticket_id}/comments",
                          {"content": reason, "isPublic": False})
        except Exception:
            pass  # non-fatal — proceed to close

    result = _zoho_request("PATCH", f"/tickets/{ticket_id}", {"status": "Closed"})
    return {
        "action":        "closed",
        "ticket_id":     ticket_id,
        "ticket_number": result.get("ticketNumber", ""),
        "subject":       result.get("subject", ""),
        "status":        result.get("status", "Closed"),
        "url":           f"https://desk.zoho.com/agent/example-msp/tickets/{ticket_id}",
    }


def search_zoho_tickets(query: str, limit: int = 20) -> list[dict]:
    """Search Zoho Desk tickets by keyword (subject or full-text).

    Uses Zoho Desk search API. Returns up to `limit` matching tickets.

    Args:
        query: Search string (e.g. customer name, keyword, ticket title fragment).
        limit: Max results (1–50). Default 20.

    Returns list of ticket summary dicts.
    """
    limit = max(1, min(limit, 50))
    qs = urllib.parse.urlencode({"searchStr": query, "module": "tickets", "limit": str(limit)})
    result = _zoho_request("GET", f"/search?{qs}")
    tickets = result.get("data", [])
    return [_fmt_zoho_ticket(t) for t in tickets]


def _extract_alarm_name(subject: str) -> str | None:
    """Ekstrak alarm name dari subject CloudWatch.

    CloudWatch subject format umum:
      - ALARM: "my-alarm-name" in ...
      - OK: "my-alarm-name" in ...
      - [ALARM] my-alarm-name - ...
      - [OK] my-alarm-name - ...

    Returns alarm name (lowercase, stripped) atau None jika tidak ditemukan.
    """
    import re
    s = subject.strip()

    # Format: ALARM: "alarm-name" in ... atau OK: "alarm-name" in ...
    m = re.search(r'(?:alarm|ok):\s*"([^"]+)"', s, re.IGNORECASE)
    if m:
        return m.group(1).lower().strip()

    # Format: [ALARM] alarm-name - desc atau [OK] alarm-name - desc
    m = re.search(r'\[(?:alarm|ok)\]\s*([^-\n]+)', s, re.IGNORECASE)
    if m:
        return m.group(1).lower().strip()

    # Format: ALARM: alarm-name (tanpa quotes)
    m = re.search(r'(?:alarm|ok):\s*(.+?)(?:\s+in\s+|\s+-\s+|$)', s, re.IGNORECASE)
    if m:
        return m.group(1).lower().strip().strip('"').strip("'")

    return None


def _build_ok_subjects_index(dept_id: str | None = None, batch_size: int = 50) -> set[str]:
    """Fetch ticket OK/resolved dari Zoho bulan berjalan dan return
    set alarm names yang sudah OK.
    """
    ok_alarm_names: set[str] = set()
    resolved_dept = dept_id or os.environ.get("ZOHO_DESK_DEPT_ID")

    ok_patterns = [
        "ok:",
        "[ok]",
        "status changed to ok",
        "has been resolved",
        "resolved:",
        "back to normal",
        "alarm: ok",
        "is now ok",
        "no longer in alarm",
        "cleared",
        "recovery",
        "alarm state is ok",
        "alert resolved",
    ]

    def _is_ok_subject(s: str) -> bool:
        sl = s.lower()
        return any(p in sl for p in ok_patterns)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # Awal bulan berjalan
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    from_index = 0
    while True:
        params: dict = {
            "limit":   str(batch_size),
            "from":    str(from_index),
            "sortBy":  "createdTime",
        }
        if resolved_dept:
            params["departmentId"] = resolved_dept

        qs = urllib.parse.urlencode(params)
        try:
            result = _zoho_request("GET", f"/tickets?{qs}")
        except Exception:
            break

        batch = result.get("data", [])
        if not batch:
            break

        stop = False
        for t in batch:
            subject = t.get("subject", "")
            created_str = t.get("createdTime", "")
            if not created_str:
                continue

            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))

            # Stop scan jika sudah lewat ke bulan lalu
            if created < month_start:
                stop = True
                break

            if not _is_ok_subject(subject):
                continue
            alarm_name = _extract_alarm_name(subject)
            if alarm_name:
                ok_alarm_names.add(alarm_name)

        if stop:
            break

        from_index += batch_size

    return ok_alarm_names


def auto_close_cloudwatch_alerts(
    dry_run: bool = True,
    dept_id: str | None = None,
    batch_size: int = 50,
    max_close: int = 500,
) -> dict:
    """Auto-close Zoho Desk tickets yang merupakan CloudWatch automated alerts.

    Dua rule close, mana yang lebih dulu terpenuhi:
    1. ALARM sudah ada pasangan OK — close SEGERA tanpa tunggu 36 jam.
       Cara kerja: ekstrak alarm name dari subject ALARM ticket, cek apakah
       ada ticket lain (semua status) dengan subject OK untuk alarm name sama.
    2. ALARM belum ada OK tapi sudah > 36 jam sejak createdTime — close juga.

    Semua status dicek: Open, On Hold, In Progress.
    Dirancang untuk dijalankan setiap 12 jam via cron.

    Args:
        dry_run:    True (default) = preview only, tidak ada perubahan.
        dept_id:    Filter department ID. Default dari ZOHO_DESK_DEPT_ID env.
        batch_size: Jumlah ticket per page API (max 50).
        max_close:  Safety cap — berhenti setelah close sejumlah ini. Default 500.

    Returns dict dengan summary: scanned, matched, closed, errors, dan
    preview list (max 100 item).
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    cutoff_36h = now - timedelta(hours=36)
    # Filter hanya bulan berjalan
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _is_cloudwatch_alarm(subject: str) -> bool:
        """Hanya match ALARM (bukan OK) — yang perlu di-close."""
        s = subject.lower()
        # Pastikan bukan OK ticket
        if any(p in s for p in ["ok:", "[ok]", "status changed to ok",
                                  "has been resolved", "is now ok",
                                  "no longer in alarm", "back to normal"]):
            return False
        return any(p in s for p in _AUTO_CLOSE_PATTERNS_CLOUDWATCH_36H)

    resolved_dept = dept_id or os.environ.get("ZOHO_DESK_DEPT_ID")

    summary: dict = {
        "dry_run":        dry_run,
        "run_at":         now.isoformat(),
        "month":          now.strftime("%B %Y"),
        "month_start":    month_start.isoformat(),
        "cutoff_36h":     cutoff_36h.isoformat(),
        "scanned":        0,
        "matched":        0,
        "closed_ok_pair": 0,   # closed karena ada pasangan OK
        "closed_timeout": 0,   # closed karena > 36 jam
        "closed":         0,   # total
        "skipped_cap":    0,
        "errors":         0,
        "preview":        [],  # max 100 matched tickets
    }

    # Step 1: Build index alarm names yang sudah OK (bulan berjalan)
    ok_alarm_index: set[str] = set()
    try:
        ok_alarm_index = _build_ok_subjects_index(dept_id=resolved_dept,
                                                   batch_size=batch_size)
    except Exception:
        pass  # non-fatal: tanpa index ini, hanya rule 36h yang aktif

    # Step 2: Scan ALARM tickets bulan berjalan
    target_statuses = ["Open", "On Hold", "In Progress"]
    total_closed = 0

    for status in target_statuses:
        from_index = 0

        while total_closed < max_close:
            params: dict = {
                "status":  status,
                "limit":   str(batch_size),
                "from":    str(from_index),
                "sortBy":  "createdTime",
            }
            if resolved_dept:
                params["departmentId"] = resolved_dept

            qs = urllib.parse.urlencode(params)
            try:
                result = _zoho_request("GET", f"/tickets?{qs}")
            except Exception:
                summary["errors"] += 1
                break

            batch = result.get("data", [])
            if not batch:
                break

            stop_status = False
            for t in batch:
                summary["scanned"] += 1
                subject = t.get("subject", "")
                created_str = t.get("createdTime", "")
                if not created_str or not _is_cloudwatch_alarm(subject):
                    continue

                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))

                # Skip ticket di luar bulan berjalan
                if created < month_start:
                    stop_status = True
                    break

                age_hours = (now - created).total_seconds() / 3600

                # Tentukan reason close
                close_reason: str | None = None

                # Rule 1: Cek apakah alarm ini sudah ada pasangan OK
                alarm_name = _extract_alarm_name(subject)
                if alarm_name and alarm_name in ok_alarm_index:
                    close_reason = "ok_pair"

                # Rule 2: Sudah > 36 jam
                elif created <= cutoff_36h:
                    close_reason = "timeout_36h"

                if close_reason is None:
                    continue  # belum 36 jam dan belum ada OK, skip

                summary["matched"] += 1

                if len(summary["preview"]) < 100:
                    summary["preview"].append({
                        "id":           t.get("id"),
                        "number":       t.get("ticketNumber"),
                        "subject":      subject[:100],
                        "status":       status,
                        "created":      created_str[:19],
                        "age_hours":    round(age_hours, 1),
                        "close_reason": close_reason,
                        "alarm_name":   alarm_name or "",
                    })

                if dry_run:
                    # Hitung breakdown untuk preview
                    if close_reason == "ok_pair":
                        summary["closed_ok_pair"] += 1
                    else:
                        summary["closed_timeout"] += 1
                    continue

                if total_closed >= max_close:
                    summary["skipped_cap"] += 1
                    continue

                try:
                    # Tambah note sebelum close sesuai reason
                    if close_reason == "ok_pair":
                        note = "System sudah terdeteksi kembali Normal"
                    else:
                        note = "System ALARM sudah berumur 36 jam maka di close"

                    try:
                        _zoho_request(
                            "POST",
                            f"/tickets/{t['id']}/comments",
                            {"content": note, "isPublic": False},
                        )
                    except Exception:
                        pass  # non-fatal — lanjut close meskipun comment gagal

                    _zoho_request(
                        "PATCH",
                        f"/tickets/{t['id']}",
                        {"status": "Closed"},
                    )
                    total_closed += 1
                    summary["closed"] += 1
                    if close_reason == "ok_pair":
                        summary["closed_ok_pair"] += 1
                    else:
                        summary["closed_timeout"] += 1
                except Exception:
                    summary["errors"] += 1

            if stop_status:
                break

            from_index += batch_size

    # Untuk dry_run, set closed = matched untuk konsistensi
    if dry_run:
        summary["closed"] = summary["matched"]

    return summary


# ---------------------------------------------------------------------------
# Subject patterns for auto-close rules
# ---------------------------------------------------------------------------

# CloudWatch automated alerts — close after 36 hours from createdTime
# Covers all statuses (Open, On Hold, In Progress)
_AUTO_CLOSE_PATTERNS_CLOUDWATCH_36H = [
    "alarm:",
    "[alarm]",
    "alarm state",
    "cloudwatch alarm",
    "aws cloudwatch",
    "cloudwatch notification",
    "cw alarm",
    # forwarded alerts
    "fwd: alarm",
    "fwd: [alarm]",
    "re: alarm",
    # common CloudWatch subject formats
    "alarm: \"",
    "in alarm:",
]

# Patterns that should be closed after AGE_DAYS_CALENDAR days (low urgency noise)
_AUTO_CLOSE_PATTERNS_7D = [
    "invitation:",
    "updated invitation:",
    "accepted invitation:",
    "cancelled event:",
    "verification code",
    "your login code",
    " otp ",
    "has been created",
    "will expire in",
    "introducing ",
    "diskon ",
    "verify your identity",
    "tiktok shop partner center",
    "chatgpt",
    "personal access token",
]

# AWS alerts & cost anomaly — close after 7 days
_AUTO_CLOSE_PATTERNS_AWS = [
    "aws cost management: cost anomaly",
    "aws cost management: budget",
    "aws marketplace",
    "fwd: [alert] aws",
    "fwd: [dev-ops] aws",
]

# DMARC / security reports — close after 3 days
_AUTO_CLOSE_PATTERNS_DMARC = [
    "report domain:",
    "report-id:",
    "dmarc",
]

# AWS alert resolved keywords in subject
_AUTO_CLOSE_PATTERNS_RESOLVED = [
    "status changed to ok",
    "has been resolved",
    "resolved:",
    "[ok]",
    "back to normal",
]


def bulk_close_zoho_tickets(
    dry_run: bool = True,
    older_than_days: int | None = None,
    dept_id: str | None = None,
    batch_size: int = 50,
    max_close: int = 500,
) -> dict:
    """Bulk-close Zoho Desk open tickets matching noise/auto-close patterns.

    Targets three categories:
    1. Calendar invites, OTP, system notifications — older than 7 days
    2. AWS cost anomaly / alert forwards — older than 7 days
    3. DMARC / security scan reports — older than 3 days
    4. AWS alert subjects containing resolved/OK keywords — any age

    Args:
        dry_run:         True (default) = preview only, no changes made.
        older_than_days: Override minimum age for ALL patterns (days).
                         None = use per-category defaults (3 or 7 days).
        dept_id:         Department ID filter. Defaults to ZOHO_DESK_DEPT_ID env.
        batch_size:      Tickets per API page (max 50).
        max_close:       Safety cap — stop after closing this many tickets.
                         Default 500. Set higher for bulk cleanup runs.

    Returns summary dict with counts per category and list of closed ticket IDs.
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)

    def _age_cutoff(days: int) -> datetime:
        return now - timedelta(days=older_than_days if older_than_days is not None else days)

    cutoff_7d = _age_cutoff(7)
    cutoff_3d = _age_cutoff(3)

    def _matches(subject: str, patterns: list[str]) -> bool:
        s = subject.lower()
        return any(p in s for p in patterns)

    def _should_close(subject: str, created: datetime) -> tuple[bool, str]:
        s = subject.lower()
        # Resolved AWS alerts — any age
        if _matches(s, _AUTO_CLOSE_PATTERNS_RESOLVED):
            return True, "aws-resolved"
        # DMARC/security reports — 3 days
        if _matches(s, _AUTO_CLOSE_PATTERNS_DMARC) and created <= cutoff_3d:
            return True, "dmarc-report"
        # AWS alerts — 7 days
        if _matches(s, _AUTO_CLOSE_PATTERNS_AWS) and created <= cutoff_7d:
            return True, "aws-alert"
        # Calendar/system noise — 7 days
        if _matches(s, _AUTO_CLOSE_PATTERNS_7D) and created <= cutoff_7d:
            return True, "system-noise"
        return False, ""

    resolved_dept = dept_id or os.environ.get("ZOHO_DESK_DEPT_ID")
    summary: dict = {
        "dry_run": dry_run,
        "scanned": 0,
        "matched": 0,
        "closed": 0,
        "skipped_cap": 0,
        "errors": 0,
        "by_category": {},
        "preview": [],  # first 50 matches for dry_run
    }

    from_index = 0
    total_closed = 0

    while total_closed < max_close:
        params: dict = {
            "status": "Open",
            "limit": str(batch_size),
            "from": str(from_index),
            "sortBy": "createdTime",
        }
        if resolved_dept:
            params["departmentId"] = resolved_dept

        qs = urllib.parse.urlencode(params)
        try:
            result = _zoho_request("GET", f"/tickets?{qs}")
        except Exception as exc:
            summary["errors"] += 1
            break

        batch = result.get("data", [])
        if not batch:
            break

        for t in batch:
            summary["scanned"] += 1
            subject = t.get("subject", "")
            created_str = t.get("createdTime", "")
            if not created_str:
                continue

            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            should, category = _should_close(subject, created)

            if not should:
                continue

            summary["matched"] += 1
            summary["by_category"][category] = summary["by_category"].get(category, 0) + 1

            if len(summary["preview"]) < 50:
                age = (now - created).days
                summary["preview"].append({
                    "id": t.get("id"),
                    "number": t.get("ticketNumber"),
                    "subject": subject[:80],
                    "age_days": age,
                    "category": category,
                })

            if dry_run:
                continue

            if total_closed >= max_close:
                summary["skipped_cap"] += 1
                continue

            try:
                _zoho_request("PATCH", f"/tickets/{t['id']}", {"status": "Closed"})
                total_closed += 1
                summary["closed"] += 1
            except Exception:
                summary["errors"] += 1

        from_index += batch_size

        # Stop scanning if the oldest ticket in this batch is newer than
        # our youngest cutoff (3d) — nothing older will appear after this.
        oldest_in_batch = batch[-1].get("createdTime", "")
        if oldest_in_batch:
            oldest_dt = datetime.fromisoformat(oldest_in_batch.replace("Z", "+00:00"))
            # Continue scanning — tickets are sorted oldest-first so keep going
            # until we reach recent tickets or run out of data.

    return summary


# ---------------------------------------------------------------------------
# Agent pool + load-balance assignment untuk CloudWatch alerts
# ---------------------------------------------------------------------------

# Exclude akun non-engineer dari pool distribusi
_AGENT_EXCLUDE_EMAILS = {
    "user@example.com",   # CTO Example MSP — bukan support engineer
}


def fetch_active_agents(dept_id: str | None = None) -> list[dict]:
    """Fetch semua agents Zoho Desk yang aktif sebagai pool assignment.

    Returns list of {id, name, email} — sudah exclude akun non-engineer.
    """
    resolved_dept = dept_id or os.environ.get("ZOHO_DESK_DEPT_ID")
    params: dict = {"limit": "50"}
    if resolved_dept:
        params["departmentId"] = resolved_dept

    qs = urllib.parse.urlencode(params)
    try:
        result = _zoho_request("GET", f"/agents?{qs}")
    except Exception:
        return []

    agents = []
    for a in result.get("data", []):
        email = a.get("emailId", "")
        if email in _AGENT_EXCLUDE_EMAILS:
            continue
        first = a.get("firstName", "")
        last  = a.get("lastName", "")
        agents.append({
            "id":    a["id"],
            "name":  f"{first} {last}".strip(),
            "email": email,
        })
    return agents


def get_agent_open_ticket_counts(
    agents: list[dict],
    dept_id: str | None = None,
    month_start=None,
    batch_size: int = 50,
) -> dict[str, int]:
    """Hitung jumlah ticket Open bulan berjalan per agent.

    Returns dict {agent_id: count} untuk semua agent di pool.
    Dipakai untuk load-balance assignment — agent dengan count terkecil
    mendapat ticket berikutnya.
    """
    from datetime import datetime, timezone

    if month_start is None:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    resolved_dept = dept_id or os.environ.get("ZOHO_DESK_DEPT_ID")
    agent_ids = {a["id"] for a in agents}
    counts: dict[str, int] = {a["id"]: 0 for a in agents}

    from_index = 0
    while True:
        params: dict = {
            "status":  "Open",
            "limit":   str(batch_size),
            "from":    str(from_index),
            "sortBy":  "createdTime",
        }
        if resolved_dept:
            params["departmentId"] = resolved_dept

        qs = urllib.parse.urlencode(params)
        try:
            result = _zoho_request("GET", f"/tickets?{qs}")
        except Exception:
            break

        batch = result.get("data", [])
        if not batch:
            break

        stop = False
        for t in batch:
            created_str = t.get("createdTime", "")
            if created_str:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                if created < month_start:
                    stop = True
                    break

            assignee = t.get("assignee") or {}
            agent_id = assignee.get("id", "")
            if agent_id in counts:
                counts[agent_id] += 1

        if stop:
            break
        from_index += batch_size

    return counts


def assign_ticket_to_agent(ticket_id: str, agent_id: str) -> bool:
    """Assign satu ticket ke agent. Returns True jika berhasil."""
    try:
        _zoho_request("PATCH", f"/tickets/{ticket_id}", {"assigneeId": agent_id})
        return True
    except Exception:
        return False


def auto_assign_cloudwatch_alerts(
    dry_run: bool = True,
    dept_id: str | None = None,
    batch_size: int = 50,
    max_assign: int = 500,
) -> dict:
    """Assign CloudWatch ALARM tickets bulan berjalan yang belum di-assign
    ke engineer secara load-balance (yang paling sedikit ticket open dapat duluan).

    Dijalankan bersamaan dengan auto_close_cloudwatch_alerts setiap 12 jam.
    Ticket yang sudah di-assign tidak disentuh.

    Returns dict summary: scanned, assigned, errors, preview.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    resolved_dept = dept_id or os.environ.get("ZOHO_DESK_DEPT_ID")

    def _is_cloudwatch_alarm(subject: str) -> bool:
        s = subject.lower()
        if any(p in s for p in ["ok:", "[ok]", "status changed to ok",
                                  "has been resolved", "is now ok",
                                  "no longer in alarm", "back to normal"]):
            return False
        return any(p in s for p in _AUTO_CLOSE_PATTERNS_CLOUDWATCH_36H)

    summary: dict = {
        "dry_run":   dry_run,
        "run_at":    now.isoformat(),
        "month":     now.strftime("%B %Y"),
        "scanned":   0,
        "assigned":  0,
        "skipped":   0,   # sudah ada assignee
        "errors":    0,
        "preview":   [],
    }

    # Step 1: Fetch agent pool
    agents = fetch_active_agents(dept_id=resolved_dept)
    if not agents:
        summary["errors"] += 1
        return summary

    # Step 2: Hitung open ticket per agent (load balance baseline)
    counts = get_agent_open_ticket_counts(
        agents=agents,
        dept_id=resolved_dept,
        month_start=month_start,
        batch_size=batch_size,
    )

    def _pick_agent() -> dict:
        """Pilih agent dengan jumlah ticket open paling sedikit."""
        return min(agents, key=lambda a: counts.get(a["id"], 0))

    # Step 3: Scan ticket CloudWatch ALARM bulan ini yang belum di-assign
    target_statuses = ["Open", "On Hold", "In Progress"]
    total_assigned = 0

    for status in target_statuses:
        from_index = 0
        while total_assigned < max_assign:
            params: dict = {
                "status":  status,
                "limit":   str(batch_size),
                "from":    str(from_index),
                "sortBy":  "createdTime",
            }
            if resolved_dept:
                params["departmentId"] = resolved_dept

            qs = urllib.parse.urlencode(params)
            try:
                result = _zoho_request("GET", f"/tickets?{qs}")
            except Exception:
                summary["errors"] += 1
                break

            batch = result.get("data", [])
            if not batch:
                break

            stop = False
            for t in batch:
                summary["scanned"] += 1
                subject = t.get("subject", "")
                created_str = t.get("createdTime", "")

                if not created_str or not _is_cloudwatch_alarm(subject):
                    continue

                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                if created < month_start:
                    stop = True
                    break

                # Skip jika sudah ada assignee
                if t.get("assignee"):
                    summary["skipped"] += 1
                    continue

                # Pilih agent load-balance
                agent = _pick_agent()
                summary["matched"] = summary.get("matched", 0) + 1

                if len(summary["preview"]) < 100:
                    summary["preview"].append({
                        "ticket_id":     t.get("id"),
                        "number":        t.get("ticketNumber"),
                        "subject":       subject[:80],
                        "assigned_to":   agent["name"],
                        "agent_email":   agent["email"],
                        "agent_load":    counts.get(agent["id"], 0),
                    })

                if dry_run:
                    # Simulasi increment untuk dry-run load balance yang akurat
                    counts[agent["id"]] = counts.get(agent["id"], 0) + 1
                    summary["assigned"] += 1
                    continue

                if total_assigned >= max_assign:
                    break

                ok = assign_ticket_to_agent(t["id"], agent["id"])
                if ok:
                    counts[agent["id"]] = counts.get(agent["id"], 0) + 1
                    total_assigned += 1
                    summary["assigned"] += 1
                else:
                    summary["errors"] += 1

            if stop:
                break
            from_index += batch_size

    return summary



def fetch_zoho_dashboard_stats(
    dept_id: str | None = None,
    batch_size: int = 50,
) -> dict:
    """Fetch statistik ringkas Zoho Desk untuk dikirim via email summary.

    Returns:
        total_open          : jumlah ticket Open + On Hold + In Progress
        open_by_assignee    : dict {nama engineer: jumlah ticket open}
        still_open_cw       : jumlah CloudWatch ALARM tickets yang masih open
        over_36h_cw         : jumlah CloudWatch ALARM tickets open yg sudah > 36 jam
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    cutoff_36h = now - timedelta(hours=36)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    resolved_dept = dept_id or os.environ.get("ZOHO_DESK_DEPT_ID")

    def _is_cloudwatch_alarm(subject: str) -> bool:
        s = subject.lower()
        if any(p in s for p in ["ok:", "[ok]", "status changed to ok",
                                  "has been resolved", "is now ok",
                                  "no longer in alarm", "back to normal"]):
            return False
        return any(p in s for p in _AUTO_CLOSE_PATTERNS_CLOUDWATCH_36H)

    stats: dict = {
        "total_open":       0,
        "open_by_assignee": {},
        "still_open_cw":    0,
        "over_36h_cw":      0,
        "month":            now.strftime("%B %Y"),
    }

    target_statuses = ["Open", "On Hold", "In Progress"]

    for status in target_statuses:
        from_index = 0
        while True:
            params: dict = {
                "status":  status,
                "limit":   str(batch_size),
                "from":    str(from_index),
                "sortBy":  "createdTime",
            }
            if resolved_dept:
                params["departmentId"] = resolved_dept

            qs = urllib.parse.urlencode(params)
            try:
                result = _zoho_request("GET", f"/tickets?{qs}")
            except Exception:
                break

            batch = result.get("data", [])
            if not batch:
                break

            stop = False
            for t in batch:
                created_str = t.get("createdTime", "")
                if created_str:
                    created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    # Hanya hitung ticket bulan berjalan
                    if created < month_start:
                        stop = True
                        break

                stats["total_open"] += 1

                # Per-assignee count
                assignee = t.get("assignee") or {}
                first = assignee.get("firstName", "")
                last  = assignee.get("lastName", "")
                name  = f"{first} {last}".strip() or "Unassigned"
                stats["open_by_assignee"][name] = stats["open_by_assignee"].get(name, 0) + 1

                # CloudWatch stats
                subject = t.get("subject", "")
                if _is_cloudwatch_alarm(subject):
                    stats["still_open_cw"] += 1
                    if created_str:
                        created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        if created <= cutoff_36h:
                            stats["over_36h_cw"] += 1

            if stop:
                break

            from_index += batch_size

    # Sort assignee by ticket count descending
    stats["open_by_assignee"] = dict(
        sorted(stats["open_by_assignee"].items(), key=lambda x: x[1], reverse=True)
    )

    return stats


def send_autoclose_summary_email(
    close_result: dict,
    dashboard: dict,
    recipients: list[str],
    smtp_user: str | None = None,
    smtp_pass: str | None = None,
    smtp_host: str = "smtp.zoho.com",
    smtp_port: int = 465,
) -> dict:
    """Kirim email summary hasil auto-close CloudWatch alerts ke daftar penerima.

    Args:
        close_result : return value dari auto_close_cloudwatch_alerts()
        dashboard    : return value dari fetch_zoho_dashboard_stats()
        recipients   : list email penerima
        smtp_user    : SMTP username (default dari env SMTP_USER)
        smtp_pass    : SMTP password (default dari env SMTP_PASS)
        smtp_host    : SMTP host (default smtp.gmail.com)
        smtp_port    : SMTP port (default 587 / STARTTLS)

    Returns dict {sent: bool, error: str|None}
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from datetime import datetime, timezone

    _smtp_user = smtp_user or os.environ.get("SMTP_USER_ZOHO", "")
    _smtp_pass = smtp_pass or os.environ.get("SMTP_PASS_ZOHO", "")

    if not _smtp_user or not _smtp_pass:
        return {"sent": False, "error": "SMTP_USER atau SMTP_PASS tidak ditemukan di env"}

    now_wib = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M") + " UTC"
    now_obj = datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # Build email body (plain text + HTML)
    # -----------------------------------------------------------------------
    closed_total    = close_result.get("closed", 0)
    closed_ok_pair  = close_result.get("closed_ok_pair", 0)
    closed_timeout  = close_result.get("closed_timeout", 0)
    assigned_new    = close_result.get("assigned_new", 0)
    total_open      = dashboard.get("total_open", 0)
    still_open_cw   = dashboard.get("still_open_cw", 0)
    over_36h_cw     = dashboard.get("over_36h_cw", 0)
    by_assignee     = dashboard.get("open_by_assignee", {})

    # Per-engineer rows
    engineer_rows_txt = ""
    engineer_rows_html = ""
    for name, count in by_assignee.items():
        engineer_rows_txt  += f"    {name:<30} {count} ticket\n"
        engineer_rows_html += (
            f"<tr><td style='padding:4px 12px'>{name}</td>"
            f"<td style='padding:4px 12px;text-align:center'>{count}</td></tr>"
        )

    subject = f"[Zoho Auto-Close] CloudWatch Alerts Summary — {now_obj.strftime('%B %Y')} — {now_wib}"

    # Plain text
    plain = f"""
Zoho Desk — CloudWatch Alert Auto-Close Summary
Run time : {now_wib}
{'='*55}

ASSIGNMENT SESI INI (bulan berjalan)
  Ticket baru di-assign    : {assigned_new} ticket (load-balance ke semua engineer)

TICKET YANG DI-CLOSE SESI INI
  Total di-close           : {closed_total} ticket
  ├─ Close karena OK pair  : {closed_ok_pair} ticket (System kembali Normal)
  └─ Close karena 36 jam   : {closed_timeout} ticket (ALARM timeout)

STATUS ZOHO DESK BULAN INI
  Total ticket masih Open  : {total_open} ticket
  CloudWatch ALARM open    : {still_open_cw} ticket
  CloudWatch ALARM >36 jam : {over_36h_cw} ticket (belum close, cek manual)

OPEN TICKET PER ENGINEER (bulan berjalan)
{engineer_rows_txt if engineer_rows_txt else "    (tidak ada data assignee)"}
---
Email ini dikirim otomatis oleh ms-ops GitHub Actions setiap 12 jam.
""".strip()

    # HTML
    html = f"""
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333">
<h2 style="color:#c0392b">☁️ Zoho Desk — CloudWatch Alert Auto-Close Summary</h2>
<p style="color:#888;font-size:12px">Run time: {now_wib} &nbsp;|&nbsp; Scope: bulan berjalan saja</p>

<h3 style="border-bottom:2px solid #eee;padding-bottom:6px">🔀 Assignment Sesi Ini</h3>
<table style="border-collapse:collapse">
  <tr><td style="padding:4px 12px">Ticket baru di-assign</td>
      <td style="padding:4px 12px"><b style="color:#2980b9">{assigned_new} ticket</b>
      <span style="color:#888;font-size:12px"> (load-balance ke semua engineer)</span></td></tr>
</table>

<h3 style="border-bottom:2px solid #eee;padding-bottom:6px;margin-top:20px">📌 Ticket Di-Close Sesi Ini</h3>
<table style="border-collapse:collapse">
  <tr><td style="padding:4px 12px">Total di-close</td>
      <td style="padding:4px 12px"><b>{closed_total} ticket</b></td></tr>
  <tr><td style="padding:4px 12px;padding-left:24px">├─ Close karena OK pair</td>
      <td style="padding:4px 12px"><b style="color:#27ae60">{closed_ok_pair} ticket</b>
      <span style="color:#888;font-size:12px"> (System kembali Normal)</span></td></tr>
  <tr><td style="padding:4px 12px;padding-left:24px">└─ Close karena 36 jam</td>
      <td style="padding:4px 12px"><b style="color:#e67e22">{closed_timeout} ticket</b>
      <span style="color:#888;font-size:12px"> (ALARM timeout)</span></td></tr>
</table>

<h3 style="border-bottom:2px solid #eee;padding-bottom:6px;margin-top:20px">📊 Status Zoho Desk Bulan Ini</h3>
<table style="border-collapse:collapse">
  <tr><td style="padding:4px 12px">Total ticket masih Open</td>
      <td style="padding:4px 12px"><b>{total_open} ticket</b></td></tr>
  <tr><td style="padding:4px 12px">CloudWatch ALARM masih open</td>
      <td style="padding:4px 12px"><b style="color:#e74c3c">{still_open_cw} ticket</b></td></tr>
  <tr><td style="padding:4px 12px">CloudWatch ALARM sudah &gt;36 jam</td>
      <td style="padding:4px 12px"><b style="color:#c0392b">{over_36h_cw} ticket</b>
      <span style="color:#888;font-size:12px"> (belum close, perlu cek manual)</span></td></tr>
</table>

<h3 style="border-bottom:2px solid #eee;padding-bottom:6px;margin-top:20px">👤 Open Ticket per Engineer (bulan berjalan)</h3>
<table style="border-collapse:collapse;border:1px solid #ddd">
  <thead>
    <tr style="background:#f5f5f5">
      <th style="padding:6px 16px;text-align:left">Engineer</th>
      <th style="padding:6px 16px;text-align:center">Jumlah Ticket Open</th>
    </tr>
  </thead>
  <tbody>
    {engineer_rows_html if engineer_rows_html else
     "<tr><td colspan='2' style='padding:6px 16px;color:#888'>Tidak ada data</td></tr>"}
  </tbody>
</table>

<p style="margin-top:24px;font-size:12px;color:#aaa">
  Email ini dikirim otomatis oleh ms-ops GitHub Actions setiap 12 jam.<br>
  Scope: ticket bulan berjalan, non-human CloudWatch alerts saja.<br>
  Detail: <a href="https://desk.zoho.com">desk.zoho.com</a>
</p>
</body></html>
""".strip()

    # -----------------------------------------------------------------------
    # Send via SMTP
    # -----------------------------------------------------------------------
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = _smtp_user
        msg["To"]      = ", ".join(recipients)
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html,  "html"))

        with smtplib.SMTP_SSL(smtp_host, 465, timeout=30) as server:
            server.login(_smtp_user, _smtp_pass)
            server.sendmail(_smtp_user, recipients, msg.as_string())

        return {"sent": True, "error": None, "recipients": recipients}

    except Exception as exc:
        return {"sent": False, "error": str(exc), "recipients": recipients}
