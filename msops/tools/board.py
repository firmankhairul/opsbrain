"""Project-board fields for an issue.

The board is what gets looked at first — it is the index a PM clicks through at a
sync-up. Measured 2026-09-30 on acme-retail's board #46: `Weight` filled on 14 of 126
items, `Segment` empty on 36, and `Status` disagreeing with the issue's own open/closed
state on 10. None of that was reachable through tooling: there was no board tool at all,
so every field was set by hand in the web UI or not at all.

`gh project item-edit` needs four ids for one write — the project, the item, the field,
and for a single-select the option — none of which the caller has. This module resolves
all of them from the issue number and the field name, and caches the lookups so setting
four fields costs three reads instead of twelve.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path
from typing import Optional

REPO = "your-org/ms-ops"
OWNER = "your-org"

# Fields this module writes. Anything else on the board is either derived by GitHub
# (Created, Updated, Closed, Parent issue, Sub-issues progress) or belongs to the issue
# rather than the board (Title, Labels, Assignees — set with `gh issue edit`).
_WRITABLE = ("Status", "Segment", "Weight", "Due")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


# The org-wide board every customer issue lands on (created 2026-10-13). A customer with
# its own `github_project:` keeps that board instead; the weekly health report suggests a
# dedicated board once a customer carries DEDICATED_BOARD_THRESHOLD open issues.
SHARED_BOARD = 60
DEDICATED_BOARD_THRESHOLD = 15


def _manifest_board(customer: str) -> Optional[str]:
    """Raw `github_project:` value from the manifest: a number, "none", or None when absent."""
    root = Path(__file__).resolve().parents[2]
    y = root / customer.lower() / "customer.yaml"
    if not y.exists():
        return None
    m = re.search(r"^github_project:\s*(\d+|none)\b", y.read_text(), re.MULTILINE)
    return m.group(1) if m else None


def dedicated_board(customer: str) -> Optional[int]:
    """`github_project:` from the customer manifest, or None when the customer has none."""
    v = _manifest_board(customer)
    return int(v) if v and v.isdigit() else None


def board_number(customer: str) -> Optional[int]:
    """The board this customer's issues are tracked on: its own, else the shared one.

    None when the customer folder does not exist, or when the manifest says
    `github_project: none` (board owned by another team, e.g. example-d): the tools then
    write no board at all."""
    root = Path(__file__).resolve().parents[2]
    if not (root / customer.lower() / "customer.yaml").exists():
        return None
    if _manifest_board(customer) == "none":
        return None
    return dedicated_board(customer) or SHARED_BOARD


def _project(board: int) -> dict:
    r = _run(["gh", "project", "view", str(board), "--owner", OWNER, "--format", "json"])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    return json.loads(r.stdout or "{}")


def _fields(board: int) -> dict:
    """Field name -> {id, type, options{name: id}}."""
    r = _run(["gh", "project", "field-list", str(board), "--owner", OWNER,
              "--format", "json"])
    if r.returncode != 0:
        return {}
    out = {}
    for f in json.loads(r.stdout or "{}").get("fields", []):
        out[f["name"]] = {
            "id": f["id"], "type": f.get("type", ""),
            "options": {o["name"]: o["id"] for o in (f.get("options") or [])},
        }
    return out


def _item_id(board: int, number: int) -> Optional[str]:
    r = _run(["gh", "project", "item-list", str(board), "--owner", OWNER,
              "--limit", "500", "--format", "json"])
    if r.returncode != 0:
        return None
    for it in json.loads(r.stdout or "{}").get("items", []):
        c = it.get("content") or {}
        if c.get("type") == "Issue" and c.get("number") == number:
            return it.get("id")
    return None


def _value_flags(field: dict, value) -> list[str] | str:
    """The right value flag for this field's type, or an error string.

    A single-select is matched against its declared options rather than sent as text:
    `gh` accepts a bad option id and the write then lands as empty, which looks like it
    worked.
    """
    t = field["type"]
    if "SingleSelect" in t:
        opt = field["options"].get(str(value))
        if opt is None:
            return (f"'{value}' bukan pilihan yang ada; yang tersedia: "
                    + ", ".join(sorted(field["options"])))
        return ["--single-select-option-id", opt]
    if "Date" in t or str(value).count("-") == 2 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
        return ["--date", str(value)]
    try:
        return ["--number", str(float(value))]
    except (TypeError, ValueError):
        return ["--text", str(value)]


def set_board_fields(customer: str, number: int, status: Optional[str] = None,
                     segment: Optional[str] = None, weight: Optional[float] = None,
                     due: Optional[str] = None, dry_run: bool = True) -> dict:
    """Set project-board fields on one issue.

    customer: registry slug — the board is read from its `customer.yaml`
    number:   issue number
    status:   Pending Approval | Todo | In Progress | Done
    segment:  Project | Monthly Report | Incident | Change | BAU
    board:    the customer's `github_project:` when it has one, else the shared board
              (SHARED_BOARD); on the shared board the Customer field is set as well
    weight:   the number from the issue's `Bobot kerja` line. The markdown is canonical;
              this is the sortable mirror, so pass the same value rather than a new one.
    due:      YYYY-MM-DD

    Only the fields you pass are touched. Returns per-field results so a partial failure
    is visible instead of being hidden behind one status.
    """
    want = {k: v for k, v in (("Status", status), ("Segment", segment),
                              ("Weight", weight), ("Due", due)) if v is not None}
    if not want:
        return {"error": "tidak ada field yang diberikan — "
                         "beri status, segment, weight, atau due"}

    board = board_number(customer)
    if board is None:
        return {"error": f"{customer} tidak punya board: customer tidak dikenal "
                         f"(tidak ada {customer}/customer.yaml) atau github_project: none"}

    fields = _fields(board)
    # On the shared board the Customer column is what makes per-customer views possible,
    # so it is set alongside whatever else was asked, when the option exists.
    if board == SHARED_BOARD and "Customer" in fields \
            and customer.lower() in fields["Customer"].get("options", {}):
        want = {**want, "Customer": customer.lower()}
    missing = [k for k in want if k not in fields]
    if missing:
        return {"error": f"board #{board} tidak punya field: {', '.join(missing)}",
                "available": sorted(fields)}

    # Validate every value before writing any of them: a half-applied change is worse
    # than a refused one, because nobody can tell which half landed.
    flags: dict[str, list[str]] = {}
    for name, value in want.items():
        f = _value_flags(fields[name], value)
        if isinstance(f, str):
            return {"error": f"{name}: {f}"}
        flags[name] = f

    out: dict = {"customer": customer, "board": board, "issue": number,
                 "dry_run": dry_run, "fields": want}
    if dry_run:
        out["plan"] = [f"{k} -> {v}" for k, v in want.items()]
        return out

    item = _item_id(board, number)
    if item is None:
        # A freshly created issue is NOT on the board automatically — found the first
        # time this ran live, on #355. Telling the caller to "add it to the board first"
        # was a dead end: there was no tool for that step. Adding it here keeps the
        # chain unbroken, and it is idempotent for an issue already present.
        add = _run(["gh", "project", "item-add", str(board), "--owner", OWNER,
                    "--url", f"https://github.com/{REPO}/issues/{number}"])
        if add.returncode != 0:
            return {**out, "error": f"issue #{number} belum di board #{board} dan "
                                    f"gagal ditambahkan: {add.stderr.strip()}"}
        out["added_to_board"] = True
        item = _item_id(board, number)
        if item is None:
            return {**out, "error": f"issue #{number} ditambahkan ke board #{board} "
                                    "tapi item-nya tidak ditemukan setelahnya"}
    proj = _project(board)
    if "error" in proj:
        return {**out, **proj}

    results = {}
    for name, fl in flags.items():
        r = _run(["gh", "project", "item-edit", "--id", item,
                  "--project-id", proj["id"], "--field-id", fields[name]["id"], *fl])
        results[name] = "ok" if r.returncode == 0 else r.stderr.strip()
    out["results"] = results
    out["ok"] = all(v == "ok" for v in results.values())
    return out


# The decision `issue_classify` records in its ACTION comment. The weight line it writes
# ("5 — dasar 3 × produksi (1,5)") does not name the task type, and a base of 3 or 8 is
# shared by a change and an incident, so the comment is the only place the type survives.
_KLASIFIKASI = re.compile(r"\*\*Klasifikasi:\*\*\s*([a-z-]+)", re.IGNORECASE)
# Older weight lines did name it: "12 — `change-high` (8) × produksi (1,5)".
_TYPE_IN_WEIGHT = re.compile(r"Bobot kerja:\*\*[^\n]*?\b(change-low|change-high|check|"
                             r"incident|insiden)\b", re.IGNORECASE)


def derive_board_fields(iss: dict, body: Optional[str] = None) -> dict:
    """Status, Weight and Segment as the issue itself states them. Pure.

    The body is canonical and the board its mirror, so every value comes from the issue:
    Status from the banner (or the closed state), Weight from `Bobot kerja`, Segment from
    a `project:*` label, else the latest `issue_classify` decision, else a task type
    named in the weight line. A value that cannot be derived is left out rather than
    guessed, so an existing board value is never overwritten with a guess.
    """
    from msops.tools import banner
    from msops.tools.integrations import _board_segment, _board_status
    from msops.tools.weight_report import parse_weight

    body = iss.get("body") or "" if body is None else body
    out: dict = {}
    if (iss.get("state") or "").upper() == "CLOSED":
        out["status"] = "Done"
    else:
        m = banner.STATUS.search(body)
        st = _board_status(m.group(2)) if m else None
        if st:
            out["status"] = st
    w, state = parse_weight(body)
    if state == "ok":
        out["weight"] = w

    labels = [l.get("name", "") for l in iss.get("labels") or [] if isinstance(l, dict)]
    seg = "Project" if any(l.startswith("project:") for l in labels) else None
    if seg is None:
        for c in reversed(iss.get("comments") or []):
            text = c.get("body") or ""
            m = _KLASIFIKASI.search(text)
            if m:
                seg = "Project" if "Segment Project" in text else _board_segment(m.group(1))
                break
    if seg is None:
        m = _TYPE_IN_WEIGHT.search(body)
        if m:
            t = m.group(1).lower()
            seg = _board_segment("incident" if t == "insiden" else t)
    if seg:
        out["segment"] = seg
    return out


def sync_board(iss: dict, body: Optional[str] = None) -> dict:
    """Mirror the issue onto its board after a writer changed it. Never raises.

    Called at the end of the writers so the board stops depending on someone remembering
    `issue_set_board_fields`: on 2026-10-15 210 of 400 board items had no Segment and 332
    no Weight. The issue is the deliverable and the board its mirror, so a board failure
    is reported in the result and never undoes the write that came before it.
    """
    labels = [l.get("name", "") for l in iss.get("labels") or [] if isinstance(l, dict)]
    customer = next((l.split(":", 1)[1] for l in labels if l.startswith("customer:")), "")
    if not customer:
        return {"skipped": "issue tidak punya label customer:<slug>"}
    try:
        if board_number(customer) is None:
            return {"skipped": f"{customer} tidak punya board"}
        fields = derive_board_fields(iss, body)
        if not fields:
            return {"skipped": "tidak ada field yang bisa diturunkan dari issue"}
        r = set_board_fields(customer, iss["number"], dry_run=False, **fields)
    except Exception as e:  # noqa: BLE001 - the board must never undo the issue write
        return {"error": f"{type(e).__name__}: {e}"}
    if r.get("ok"):
        return {"applied": fields}
    return {"error": r.get("error") or r.get("results"), "attempted": fields}
