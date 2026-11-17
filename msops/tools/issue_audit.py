"""Read-only audit of GitHub Issue bodies against the 6-block standard.

Defined in docs/standards/ops-issue-format.md. This is the measuring instrument
for that standard: it answers "which issues do not conform, and what exactly
should change" without touching anything.

Why it exists as a tool rather than an ad-hoc script: the same analysis was
rewritten four times as throwaway Python while auditing acme-retail (heading
vocabulary, weight coverage, body length, state-versus-banner contradictions).
Progress on the standard is not visible unless it can be measured repeatedly.

The hazard being measured is the one from #316 and #343: a body that contradicts
reality. A reader — human or agent — who trusts it acts on a wrong answer. So the
findings are ordered by how badly they mislead, not by how untidy they look.
"""
from __future__ import annotations
import json
import re
import subprocess
from datetime import date
from typing import Optional

from msops.tools.action_status import is_done

REPO = "your-org/ms-ops"

# A body should read on one screen. Kept as reported data and as a weak fallback
# signal only: length is a symptom, not the defect. The defect is REGISTER — a body
# written at execution level instead of summary level. 40 lines of CLI output is
# worse than 60 lines of summary, so the findings below key on the shape of the
# content, not on how much of it there is.
BODY_LINE_TARGET = 40
# The threshold for the weak "verbose" finding, deliberately far above the target: a
# 55-line body of clean summary is not a defect, so flagging it would be crying wolf
# on exactly the issues that were curated properly (#316, #109, #319). Only a body
# this far over is too much prose regardless of what shape the content takes.
VERBOSE_LINES = 120

# Tables that belong in the body no matter how long: Environment carries the
# identifiers that make an old issue findable (the #343 rule), and Action items IS
# the progress map. Every other long table is a raw inventory.
_TABLE_KEEP = ("environment", "action items")
# A table bigger than this, outside those two blocks, is an inventory rather than a
# summary — 18 volumes, 40 instances, 121 rows in #154.
_RAW_TABLE_ROWS = 8

_FENCE = re.compile(r"^\s*```")
_TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
# A numbered row in the action-items table, used to count what is still pending.
_ACTION_ROW = re.compile(r"^\|\s*\d+\s*\|.*$", re.MULTILINE)
# Pictographs and the symbol blocks the old status words used (✅ ⬜ 🔄 🔴 ⚠️ ⏳).
# Plain punctuation like · → — stays outside these ranges.
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u231A-\u23FF]")
# "4.1 — Manifests", "Step 3", "Checklist (isi/centang saat eksekusi)" — a procedure
# to follow, which is what a MoP is for.
_STEP_HEADING = re.compile(r"^(\d+\.\d|step\s|langkah\s|checklist)", re.IGNORECASE)

# The 5 blocks. Block 5 is titled "Root cause" for incidents and
# "Catatan & keputusan" for changes, so either satisfies it.
BLOCK_ALIASES: dict[str, tuple[str, ...]] = {
    "Environment": ("environment",),
    "Masalah": ("masalah",),
    "Action items": ("action items",),
    "Block 5 (Root cause / Catatan)": ("root cause", "catatan & keputusan", "catatan"),
}
# History is mandatory in a ticket file but NOT part of the high-level body — it is
# a dated trail, which the standard puts in comments. Tracked separately so the
# audit can flag it as "move out" rather than "missing".
HISTORY_ALIASES = ("riwayat", "status history")

_BANNER_STATUS = re.compile(r"^>\s*\*\*status:?\*\*:?\s*(.+)", re.MULTILINE | re.IGNORECASE)
_BANNER_UPDATED = re.compile(r"^>\s*\*\*update terakhir:?\*\*", re.MULTILINE | re.IGNORECASE)
_WEIGHT = re.compile(r"\*\*bobot kerja:?\*\*\s*(.+)", re.IGNORECASE)
_WEIGHT_NUM = re.compile(r"\*\*bobot kerja:?\*\*\s*(\d+)", re.IGNORECASE)
_HEADING = re.compile(r"^#{2,3}\s+(.+?)\s*$", re.MULTILINE)

# The five questions a PM asks in a sync-up, and what in the body answers each. The
# body has to answer them WITHOUT opening comments — that is the acceptance test, and
# it outranks every cosmetic finding.
_PM_QUESTIONS: dict[str, tuple[str, str]] = {
    "di mana ini berdiri": ("status",   r"^>\s*\*\*status:?\*\*:?\s*\S"),
    "bola di siapa":       ("bola di",  r"\*\*bola di:?\*\*:?\s*[^\s·|]"),
    "next step apa":       ("next",     r"\*\*next:?\*\*:?\s*[^\s·|]"),
    "update terakhir":     ("update",   r"\*\*update terakhir:?\*\*:?\s*\S"),
    "PIC per action item": ("pic",      r"\|\s*PIC\s*\|"),
}
# Open, has pending work, and nothing has moved for this long: the PM's first question.
STALE_DAYS = 21

# An unchecked checkbox in a comment. This is the #316 failure mode in its original
# form — work piling up in comments while the body stays frozen. #154 had 15 of them in
# one comment from 18 August, invisible to every tool until someone read the thread.
_COMMENT_TODO = re.compile(r"^\s*[-*]\s+\[ \]\s+(.*\S)\s*$", re.MULTILINE)
# Archive comments hold the old body verbatim, checkboxes included. Those are history,
# not live work, so everything inside a <details> block is ignored.
_DETAILS = re.compile(r"<details>.*?</details>", re.DOTALL | re.IGNORECASE)

# Statuses that mean the work is finished, matched on the FIRST word — the same
# rule ticket_file_sync_to_issue uses to decide open-versus-closed.
_DONE_WORDS = ("resolved", "closed", "done", "selesai")

# Where each legacy heading should end up. Built from the 361 non-standard names
# actually in use across the 132 acme-retail issues, most frequent first, so the
# advice is a rename/move instruction instead of "does not conform".
#   rename -> same content, standard name
#   merge  -> fold into an existing block
#   move   -> out of the body entirely (dated comment, or a linked .md file)
HEADING_ADVICE: dict[str, tuple[str, str]] = {
    "status history":      ("move",   "comment bertanggal (atau biarkan di ticket file)"),
    "riwayat":             ("move",   "ticket file saja — body issue tidak punya ## Riwayat, duplikat banner"),
    # Dropped as a block on 2026-09-30: nothing maintained it, so it rotted. Evidence
    # now rides on the action-item row; standing docs go to Environment.
    "referensi":           ("move",   "dibongkar — link bukti ke baris Action items, dokumen tetap ke row `Dokumen` di ## Environment"),
    "related documents":   ("move",   "dibongkar — link bukti ke baris Action items, dokumen tetap ke row `Dokumen` di ## Environment"),
    "reference":           ("move",   "dibongkar — link bukti ke baris Action items, dokumen ke row `Dokumen`"),
    "references":          ("move",   "dibongkar — link bukti ke baris Action items, dokumen ke row `Dokumen`"),
    "issue":               ("rename", "## Masalah"),
    "description":         ("merge",  "## Masalah"),
    "objective":           ("merge",  "## Masalah"),
    "summary":             ("merge",  "## Masalah"),
    "scope":               ("merge",  "## Masalah"),
    "investigation":       ("move",   "comment bertanggal — jejak, bukan keadaan sekarang"),
    "analysis":            ("move",   "comment bertanggal"),
    "analysis — root cause": ("rename", "## Root cause"),
    "resolution":          ("move",   "comment bertanggal; hasilnya ke ## Action items"),
    "result":              ("merge",  "## Action items"),
    "action items":        ("rename", "## Action items (huruf kecil 'items')"),
    "root cause":          ("rename", "## Root cause (huruf kecil 'cause')"),
    "notes":               ("rename", "## Catatan & keputusan"),
    "catatan":             ("rename", "## Catatan & keputusan"),
    "status":              ("merge",  "status banner (blok 1)"),
    "instance":            ("merge",  "## Environment"),
    "instances":           ("merge",  "## Environment"),
    "raci":                ("move",   ".md file, di-link dari row `Dokumen` di ## Environment"),
    "risk assessment":     ("move",   ".md file, di-link dari row `Dokumen` di ## Environment"),
    "email to customer":   ("move",   "comment — komunikasi, bukan keadaan sekarang"),
    "recommendation":      ("rename", "## Catatan & keputusan"),
    "recommendation (not executed)": ("rename", "## Catatan & keputusan"),
}


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def _advice_for(heading: str) -> tuple[str, str]:
    """Return (kind, target) for a non-standard heading.

    Exact match first, then a prefix match so dated one-offs like
    "Current State (verified live 2026-09-07)" and "Ringkasan Status (per ...)"
    resolve to the same advice as their undated form instead of falling through
    to the generic default.
    """
    h = heading.strip().lower()
    if h in HEADING_ADVICE:
        return HEADING_ADVICE[h]
    for known, advice in HEADING_ADVICE.items():
        if h.startswith(known):
            return advice
    # Everything else is one-off prose. It is not wrong to have written it, but it
    # does not belong in a body that must answer "where does this stand".
    return ("move", "comment atau .md file — bukan salah satu dari 5 blok")


def detail_signals(body: str) -> list[dict]:
    """Find content written at execution level rather than summary level.

    This is the register check. Each signal names what the content is and where it
    belongs, because the body is meant to answer "where does this stand" while the
    detail stays reachable — in a dated comment, or in a linked .md file.

    Deliberately narrow: only shapes that are unambiguously detail. Dated narrative
    prose was considered and dropped — zero of the 132 acme-retail bodies had it, so
    a detector for it would only be a source of false positives.
    """
    out: list[dict] = []
    section = "(awal body)"
    fence_open = False
    fence_lines = 0
    fence_section = section
    table_rows = 0
    table_section = section

    def flush_table():
        nonlocal table_rows
        low = table_section.lower()
        # History tables are already handled by HEADING_ADVICE, which sends them to a
        # dated comment. Flagging them here too would double-report them AND give the
        # wrong destination (.md file).
        if table_rows > _RAW_TABLE_ROWS and \
                not any(low.startswith(k) for k in _TABLE_KEEP) and \
                not any(low.startswith(h) for h in HISTORY_ALIASES):
            out.append({
                "kind": "raw-table",
                "where": table_section,
                "size": table_rows,
                "advice": f"tabel {table_rows} baris = inventaris mentah → .md file, "
                          "sisakan 1 baris ringkasan + link",
            })
        table_rows = 0

    for line in (body or "").splitlines():
        if _FENCE.match(line):
            if fence_open:
                if fence_lines > 2:
                    out.append({
                        "kind": "code-block",
                        "where": fence_section,
                        "size": fence_lines,
                        "advice": f"blok {fence_lines} baris (perintah/output/manifest) → "
                                  "comment kalau itu bukti eksekusi, .md file kalau itu konfigurasi",
                    })
                fence_open = False
                fence_lines = 0
            else:
                fence_open, fence_lines, fence_section = True, 0, section
            continue
        if fence_open:
            fence_lines += 1
            continue

        m = _HEADING.match(line)
        if m:
            flush_table()
            section = m.group(1).strip()
            table_section = section
            if _STEP_HEADING.match(section):
                out.append({
                    "kind": "execution-steps",
                    "where": section,
                    "size": 0,
                    "advice": "prosedur langkah-demi-langkah → MoP (.md file), "
                              "body cukup menyebut fase mana yang jalan",
                })
            continue

        if line.strip().startswith("|") and not _TABLE_SEP.match(line):
            if table_rows == 0:
                table_section = section
            table_rows += 1
        elif not line.strip():
            pass
        else:
            flush_table()

    flush_table()
    if fence_open and fence_lines > 2:
        out.append({"kind": "code-block", "where": fence_section, "size": fence_lines,
                    "advice": "blok kode tidak tertutup — periksa body"})
    return out


def pending_in_comments(comments: list[dict], body: str) -> list[str]:
    """Unchecked `- [ ]` items in comments that the body's action-items table does not
    cover.

    The body is supposed to be the progress map. An open item that lives only in a
    comment is invisible: it does not show up in the table a PM reads, and
    `list_open_action_items` only scans local files, so nothing surfaces it at all.
    """
    rows = " ".join(_ACTION_ROW.findall(body or "")).lower()
    out: list[str] = []
    for c in comments or []:
        text = _DETAILS.sub("", c.get("body") or "")
        for item in _COMMENT_TODO.findall(text):
            t = item.strip()
            # A loose containment check: if the gist already appears in a table row the
            # item is covered. Matching on the first few words keeps "Ubah health check
            # path TG tax" from being counted twice when the row words it differently.
            key = " ".join(re.sub(r"[`*_\[\]()]", "", t).lower().split()[:4])
            if key and key not in rows:
                out.append(t)
    return out


def audit_body(number: int, title: str, state: str, body: str,
               board: Optional[dict] = None, updated_at: Optional[str] = None,
               today: Optional[str] = None,
               comments: Optional[list[dict]] = None,
               customer: Optional[str] = None) -> dict:
    """Audit one issue body. Pure function — no network, so it is testable.

    `board` is the optional project-board row: {"status": ..., "segment": ...,
    "weight": ...}. Board data is what makes the state contradictions visible
    (#154 was Done on the board while the issue stayed open), so it is folded
    into the findings when present.

    `customer` enables the scope finding, and only for a customer whose
    customer.yaml names a `sow:`. Passed as None the function stays exactly as it
    was — an issue is not in violation for lacking a verdict against a contract
    that is not in the repo.
    """
    body = body or ""
    lines = body.splitlines()
    headings = [h.strip() for h in _HEADING.findall(body)]
    lowered = [h.lower() for h in headings]

    present, missing = [], []
    for block, aliases in BLOCK_ALIASES.items():
        if any(any(l == a or l.startswith(a) for a in aliases) for l in lowered):
            present.append(block)
        else:
            missing.append(block)

    m = _BANNER_STATUS.search(body)
    banner_status = m.group(1).split("·")[0].strip() if m else None

    wm = _WEIGHT.search(body)
    weight_raw = wm.group(1).strip() if wm else None
    wn = _WEIGHT_NUM.search(body)
    weight = int(wn.group(1)) if wn else None

    nonstandard = []
    for h in headings:
        l = h.lower()
        if any(l == a or l.startswith(a) for aliases in BLOCK_ALIASES.values() for a in aliases):
            # Case and wording still matter — "Action Items" is not "Action items" —
            # so a block that matched by alias can still need a rename.
            if h not in BLOCK_ALIASES and h.lower() in HEADING_ADVICE:
                kind, target = HEADING_ADVICE[h.lower()]
                if kind == "rename" and h not in ("Root cause", "Action items"):
                    nonstandard.append({"heading": h, "action": kind, "target": target})
            continue
        if l in HISTORY_ALIASES:
            kind, target = _advice_for(h)
            nonstandard.append({"heading": h, "action": kind, "target": target})
            continue
        kind, target = _advice_for(h)
        nonstandard.append({"heading": h, "action": kind, "target": target})

    # Computed before the findings because the missing-block gate needs it: a body
    # only needs the 6-block skeleton once it actually holds content.
    signals = detail_signals(body)

    # Findings, most-misleading first. The order is the point: a body that
    # contradicts the issue state makes a reader act wrongly, while a heading
    # named "Notes" instead of "Catatan & keputusan" only makes them scroll.
    findings: list[dict] = []

    if banner_status:
        first = banner_status.split()[0].lower().strip("*_`") if banner_status.split() else ""
        says_done = first in _DONE_WORDS
        if state.upper() == "CLOSED" and not says_done:
            findings.append({
                "severity": "contradiction",
                "detail": f"issue CLOSED tapi banner bilang '{banner_status}' — "
                          "pembaca yang percaya body dapat jawaban salah (pola #316)",
            })
        if state.upper() == "OPEN" and says_done:
            findings.append({
                "severity": "contradiction",
                "detail": f"issue OPEN tapi banner bilang '{banner_status}' — "
                          "selesaikan salah satu: tutup issue, atau perbarui banner",
            })

    # The acceptance test: which of the five PM questions the body cannot answer.
    # Reported before anything cosmetic, because this is the whole point.
    has_action_table = bool(re.search(r"^#{2,3}\s*action items", body, re.I | re.M))
    unanswered = []
    for q, (key, pat) in _PM_QUESTIONS.items():
        # "PIC per action item" only applies when there IS an action-items table. An
        # umbrella that points at native sub-issues answers "whose ball" through its
        # children, so demanding a PIC column there would be a false positive.
        if key == "pic" and not has_action_table:
            continue
        if not re.search(pat, body, re.IGNORECASE | re.MULTILINE):
            unanswered.append(q)
    if unanswered:
        findings.append({
            "severity": "pm-insufficient",
            "detail": "body tidak menjawab: " + " · ".join(unanswered)
                      + f" ({len(unanswered)} dari 5) — PM harus buka comment atau nanya orang",
            "unanswered": unanswered,
        })

    # The #316 failure mode, caught directly: open work that exists only in a comment.
    # Ranked just below a contradiction because the effect is the same — the body a PM
    # trusts is not telling the whole story.
    orphan = pending_in_comments(comments or [], body)
    if orphan:
        findings.append({
            "severity": "pending-in-comment",
            "detail": f"{len(orphan)} action item terbuka hanya ada di comment, tidak di "
                      f"tabel Action items: {'; '.join(x[:48] for x in orphan[:3])}"
                      + (" …" if len(orphan) > 3 else ""),
            "items": orphan,
        })

    # Idle: open, still has pending work, and nothing has moved. 24 of 66 acme-retail
    # issues were in this state on 2026-09-30, up to 70 days, and it showed up nowhere.
    idle_days = None
    if updated_at:
        try:
            ref = date.fromisoformat((today or date.today().isoformat())[:10])
            idle_days = (ref - date.fromisoformat(updated_at[:10])).days
        except ValueError:
            idle_days = None
    pending_rows = len([r for r in _ACTION_ROW.findall(body)
                        if not is_done(r.strip().strip("|").split("|")[-1])])
    if state.upper() == "OPEN" and idle_days is not None and idle_days >= STALE_DAYS:
        findings.append({
            "severity": "stale",
            "detail": f"{idle_days} hari tanpa update"
                      + (f", {pending_rows} action item masih pending" if pending_rows else "")
                      + " — tidak ada checkpoint",
        })

    found = sorted(set(_EMOJI.findall(f"{title}\n{body}")))
    if found:
        findings.append({
            "severity": "emoji",
            "detail": f"emoji di judul/body: {' '.join(found)} — pakai kata "
                      "(Done/In Progress/Pending/Blocker), lihat ops-issue-format.md",
        })

    if board:
        bs = (board.get("status") or "").strip()
        if bs == "Done" and state.upper() == "OPEN":
            findings.append({"severity": "contradiction",
                             "detail": "board Status=Done tapi issue masih OPEN"})
        if bs and bs != "Done" and state.upper() == "CLOSED":
            findings.append({"severity": "contradiction",
                             "detail": f"issue CLOSED tapi board Status={bs}"})
        if not bs:
            findings.append({"severity": "board-field",
                             "detail": "board Status kosong — item tidak muncul di kolom mana pun"})
        if not (board.get("segment") or "").strip():
            findings.append({"severity": "board-field",
                             "detail": "board Segment kosong — board tidak bisa di-group per jenis kerja"})

    if customer:
        from msops.tools.scope import has_sow, parse_scope
        if has_sow(customer):
            _sv, _, _sst = parse_scope(body)
            if _sst == "absent":
                findings.append({
                    "severity": "scope",
                    "detail": "tidak ada baris 'Scope' — tidak terhitung di daftar "
                              "aktivitas luar-SoW; issue ini dibuat sebelum aturan "
                              "scope berlaku"})
            elif _sst == "undecided":
                findings.append({
                    "severity": "scope",
                    "detail": "baris 'Scope' masih placeholder — belum ada yang "
                              "memutuskan dalam atau di luar SoW"})
            elif _sst == "no-reason":
                findings.append({
                    "severity": "scope",
                    "detail": "ditandai di luar SoW tanpa menyebut klausanya — "
                              "tanpa itu baris ini tidak bisa dipakai sales"})
            elif _sst == "unparseable":
                findings.append({
                    "severity": "scope",
                    "detail": "baris 'Scope' tidak terbaca — pakai 'dalam SoW' "
                              "atau 'di luar SoW — <klausa>'"})

    if weight is None:
        if weight_raw:
            findings.append({
                "severity": "weight",
                "detail": f"Bobot kerja masih placeholder ('{weight_raw[:40]}') — regex agregasi "
                          "cari angka, jadi issue ini hilang dari total tanpa warning",
            })
        else:
            findings.append({"severity": "weight",
                             "detail": "tidak ada baris 'Bobot kerja' — tidak terhitung di capacity planning"})

    # Missing blocks are only reported for a body that is ALREADY too long. The
    # blocks exist to organise content, so "470 lines and still no Action items
    # table" is a real defect, while "3 lines and no Environment table" is not —
    # a short body that points at the detail is the goal, not a violation. Telling
    # #80 (3 lines) to add five empty sections would contradict the standard it is
    # meant to enforce. `blocks_missing` is still returned either way, so anyone who
    # wants the raw picture has it.
    if missing and (signals or len(lines) > VERBOSE_LINES):
        findings.append({"severity": "missing-block",
                         "detail": "blok hilang: " + ", ".join(missing)})

    # Register, not length. A body holding execution-level content is the defect;
    # the line count is only how it shows up.
    if signals:
        kinds: dict[str, int] = {}
        for s in signals:
            kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
        findings.append({
            "severity": "detail-in-body",
            "detail": "body memuat materi level eksekusi: "
                      + ", ".join(f"{v}× {k}" for k, v in kinds.items())
                      + " — pindahkan, detailnya tetap terbaca dari comment / .md file",
        })

    movable = [n["heading"] for n in nonstandard if n["action"] == "move"]
    if not signals and len(lines) > VERBOSE_LINES:
        # Long, but nothing is shaped like detail — so it is verbose prose rather
        # than misplaced content. Weakest finding there is, and reported last.
        hint = f"; kandidat dipindah: {', '.join(movable[:4])}" if movable else ""
        findings.append({
            "severity": "verbose",
            "detail": f"{len(lines)} baris tanpa blok detail yang jelas — "
                      f"prosa terlalu banyak untuk body ringkasan{hint}",
        })

    if nonstandard:
        findings.append({
            "severity": "heading",
            "detail": f"{len(nonstandard)} heading di luar kosakata standar",
        })

    return {
        "number": number,
        "title": title,
        "state": state,
        "lines": len(lines),
        "banner_status": banner_status,
        "weight": weight,
        "weight_raw": weight_raw,
        "pending_in_comments": orphan,
        "idle_days": idle_days,
        "pending_action_items": pending_rows,
        "blocks_present": present,
        "blocks_missing": missing,
        "nonstandard_headings": nonstandard,
        "detail_signals": signals,
        "findings": findings,
        "conforms": not findings,
    }


def _fetch_issues(customer: str, number: Optional[int]) -> list[dict] | dict:
    if number is not None:
        r = _run(["gh", "issue", "view", str(number), "--repo", REPO,
                  "--json", "number,title,state,body,updatedAt,comments"])
        if r.returncode != 0:
            return {"error": r.stderr.strip()}
        return [json.loads(r.stdout)]

    r = _run(["gh", "issue", "list", "--repo", REPO,
              "--label", f"customer:{customer.lower()}", "--state", "all",
              "--limit", "500", "--json", "number,title,state,body,updatedAt,comments"])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    return json.loads(r.stdout or "[]")


def _fetch_board(customer: str) -> dict[int, dict]:
    """Board rows keyed by issue number, or {} when no board is reachable.

    Only 4 of 46 customers have a board, so a missing board is normal and must
    not fail the audit — the body findings stand on their own.
    """
    board_no = _board_number(customer)
    if not board_no:
        return {}
    r = _run(["gh", "project", "item-list", str(board_no), "--owner", "your-org",
              "--limit", "500", "--format", "json"])
    if r.returncode != 0:
        return {}
    try:
        items = json.loads(r.stdout or "{}").get("items", [])
    except json.JSONDecodeError:
        return {}
    out = {}
    for it in items:
        c = it.get("content") or {}
        if c.get("type") != "Issue" or c.get("number") is None:
            continue
        out[c["number"]] = {"status": it.get("status"), "segment": it.get("segment"),
                            "weight": it.get("weight")}
    return out


def _board_number(customer: str) -> Optional[int]:
    """Read `github_project:` from the customer manifest. Not every customer has one."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    y = root / customer.lower() / "customer.yaml"
    if not y.exists():
        return None
    m = re.search(r"^github_project:\s*(\d+)", y.read_text(), re.MULTILINE)
    return int(m.group(1)) if m else None


def audit_issue_format(customer: str, number: Optional[int] = None,
                       only_violations: bool = True, limit: int = 0) -> dict:
    """Audit GitHub Issue bodies against docs/standards/ops-issue-format.md.

    Read-only: fetches issues via `gh`, reads the project board when the customer
    has one, and reports per-issue findings with the specific fix for each. Writes
    nothing.

    customer:        registry slug, e.g. "acme-retail" (drives the customer:<slug> label)
    number:          audit a single issue instead of the whole customer
    only_violations: omit conforming issues from `issues` (the summary still counts them)
    limit:           cap the reported issues (0 = all); worst-first, so a cap keeps the
                     issues most worth fixing
    """
    issues = _fetch_issues(customer, number)
    if isinstance(issues, dict):
        return issues
    board = _fetch_board(customer)

    audited = [audit_body(i["number"], i.get("title", ""), i.get("state", ""),
                          i.get("body") or "", board.get(i["number"]),
                          updated_at=i.get("updatedAt"),
                          comments=i.get("comments"), customer=customer)
               for i in issues]

    # Ordered by how badly each misleads a PM reading the body, not by untidiness.
    sev = {"contradiction": 0, "pending-in-comment": 1, "pm-insufficient": 2, "stale": 3,
           "detail-in-body": 4, "weight": 5, "scope": 6, "board-field": 7,
           "missing-block": 8, "heading": 9, "verbose": 10, "emoji": 11}
    def worst(a: dict) -> tuple:
        ranks = [sev.get(f["severity"], 9) for f in a["findings"]] or [99]
        return (min(ranks), -len(a["findings"]), -a["lines"])

    audited.sort(key=worst)

    counts: dict[str, int] = {}
    for a in audited:
        for f in a["findings"]:
            counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    heading_tally: dict[str, int] = {}
    for a in audited:
        for n in a["nonstandard_headings"]:
            heading_tally[n["heading"]] = heading_tally.get(n["heading"], 0) + 1

    weights = [a["weight"] for a in audited if a["weight"] is not None]
    reported = [a for a in audited if a["findings"]] if only_violations else audited
    if limit:
        reported = reported[:limit]

    return {
        "customer": customer,
        "board": _board_number(customer),
        "summary": {
            "issues": len(audited),
            "conforming": sum(1 for a in audited if a["conforms"]),
            "violating": sum(1 for a in audited if a["findings"]),
            "median_body_lines": _median([a["lines"] for a in audited]),
            "within_line_target": sum(1 for a in audited if a["lines"] <= BODY_LINE_TARGET),
            "pm_sufficient": sum(1 for a in audited
                                 if not any(f["severity"] == "pm-insufficient"
                                            for f in a["findings"])),
            "pending_in_comment": sum(1 for a in audited
                                      if a["pending_in_comments"]),
            "stale": sum(1 for a in audited
                         if any(f["severity"] == "stale" for f in a["findings"])),
            "with_weight": len(weights),
            "weight_total": sum(weights),
            "distinct_nonstandard_headings": len(heading_tally),
            "findings_by_severity": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        },
        "top_nonstandard_headings": dict(sorted(heading_tally.items(),
                                                key=lambda kv: -kv[1])[:20]),
        "issues": reported,
    }


def _median(xs: list[int]) -> int:
    if not xs:
        return 0
    s = sorted(xs)
    return s[len(s) // 2]
