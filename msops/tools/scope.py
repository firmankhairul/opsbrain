"""In-SoW / out-of-SoW classification for customer work.

The problem this exists for: activities outside a customer's Scope of Work get done
anyway -- refusing is rarely an option -- and nothing records that they were outside.
The customer then reasonably assumes they were included all along, and at renewal there
is no evidence to price against.

**The tool never decides.** It puts the contract in front of whoever is deciding and
records what they decided. That is not caution for its own sake: on 2026-10-07, working
with the full text of acme-retail's SoW open, a keyword tally over it returned 3 false
positives out of 4 sampled (CWAgent, IIS and K8S matched technology *names*, not
activities), and two clauses were read backwards outright -- TrendMicro appeared to be
excluded as a "Non AWS Product" while in fact having its own scope section, and "Create
a New Environment" read as an absolute bar while a separate line grants a quota of 60
resources a year. The document has overlapping clauses and no precedence rule. A matcher
over it would be confidently wrong in both directions: labelling in-scope work as
out-of-scope damages trust, and the reverse loses the money this is meant to recover.

So the same rule as `env`, `priority` and `due`: ask, never guess.

Gated per customer, by the `sow:` field in customer.yaml -- not by the presence of a SoW
file. Three customers already have SoW documents sitting in the repo (acme-retail,
acme-retail, acme-retail) and acme-retail has four of them, so "which SoW" is a real
question there and filename detection would answer it by guessing. Of 47 customers, the
field turns this on for exactly the ones someone deliberately switched on.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path
from typing import Optional

REPO = "your-org/ms-ops"
ROOT = Path(__file__).resolve().parents[2]

SCOPE_PLACEHOLDER = "<dalam SoW | di luar SoW — sebutkan klausanya>"

IN_SOW = "in-sow"
OUT_OF_SOW = "out-of-sow"

# The banner line, as it appears in a ticket and in the issue body it is derived from.
_SCOPE = re.compile(r"^>?\s*\*\*Scope:\*\*[ \t]*(.*?)[ \t]*$", re.MULTILINE)

# Verdict vocabulary. Indonesian first because that is what gets typed here; the English
# forms are accepted because the SoW documents and the labels are in English.
_OUT_WORDS = ("di luar sow", "diluar sow", "luar sow", "out of sow", "out-of-sow",
              "outside sow", "out of scope", "diluar scope", "di luar scope")
_IN_WORDS = ("dalam sow", "didalam sow", "di dalam sow", "in sow", "in-sow",
             "within sow", "dalam scope", "in scope")

_STOPWORDS = {
    "yang", "untuk", "pada", "dari", "dengan", "atau", "adalah", "akan", "tidak",
    "dan", "ini", "itu", "ada", "the", "and", "for", "with", "that", "this", "any",
    "are", "not", "other", "from", "all", "its", "which", "such", "tasks", "into",
}


def _sow_field(text: str) -> Optional[str]:
    r"""The `sow:` value, with any trailing `# comment` stripped.

    `github_project:` gets away without this because it captures `(\d+)`; a filename
    captured as `(.+)` swallows the comment and the pointer dangles.
    """
    m = re.search(r"^sow:\s*(.+?)\s*$", text, re.MULTILINE)
    if not m:
        return None
    return re.sub(r"\s+#.*$", "", m.group(1)).strip().strip('"\'')


def _manifest(customer: str, root: Optional[Path] = None) -> Optional[Path]:
    y = (root or ROOT) / customer.lower() / "customer.yaml"
    return y if y.exists() else None


def sow_path(customer: str, root: Optional[Path] = None) -> Optional[Path]:
    """The customer's SoW document, from `sow:` in customer.yaml, or None.

    None is a normal answer, not an error: it means this customer is not gated yet.
    A `sow:` that names a file which does not exist returns None as well -- a dangling
    pointer must not silently turn the gate on with nothing behind it; `sow_status`
    reports that case so it is visible rather than merely inert.
    """
    y = _manifest(customer, root)
    if y is None:
        return None
    named = _sow_field(y.read_text(encoding="utf-8"))
    if not named:
        return None
    p = (root or ROOT) / customer.lower() / named
    return p if p.exists() else None


def sow_status(customer: str, root: Optional[Path] = None) -> dict:
    """Why this customer is or is not gated -- so a typo in `sow:` is visible."""
    y = _manifest(customer, root)
    if y is None:
        return {"gated": False, "reason": f"{customer} tidak punya customer.yaml"}
    named = _sow_field(y.read_text(encoding="utf-8"))
    if not named:
        return {"gated": False,
                "reason": f"{customer}/customer.yaml belum punya field `sow:` — "
                          "scope tidak diminta dan tidak di-gate"}
    p = (root or ROOT) / customer.lower() / named
    if not p.exists():
        return {"gated": False, "sow": named,
                "reason": f"`sow: {named}` menunjuk file yang tidak ada di "
                          f"{customer}/ — perbaiki atau hapus fieldnya"}
    return {"gated": True, "sow": named, "sow_path": str(p)}


def has_sow(customer: str, root: Optional[Path] = None) -> bool:
    return sow_path(customer, root) is not None


def scope_label(verdict: str) -> str:
    """`scope:in-sow` / `scope:out-of-sow`.

    TWO labels, not one. With only `out-of-sow`, an unlabelled issue is ambiguous
    between "we decided it is in scope" and "nobody has looked" -- and at the start
    almost everything is the second. Making undecided a countable state is the point.
    """
    if verdict not in (IN_SOW, OUT_OF_SOW):
        raise ValueError(f"verdict harus {IN_SOW!r} atau {OUT_OF_SOW!r}, bukan {verdict!r}")
    return f"scope:{verdict}"


def scope_line(verdict: Optional[str] = None, reason: Optional[str] = None) -> str:
    """The `Scope` banner line, left as a placeholder when undecided.

    A placeholder parses as nothing and is reported; a half-filled line ("dalam SoW"
    with no clause) is an assertion nobody can check later, which is the failure mode
    `## Referensi` died of.
    """
    if verdict not in (IN_SOW, OUT_OF_SOW):
        return f"> **Scope:** {SCOPE_PLACEHOLDER}\n"
    word = "dalam SoW" if verdict == IN_SOW else "di luar SoW"
    tail = f" — {reason.strip()}" if reason and reason.strip() else ""
    return f"> **Scope:** {word}{tail}\n"


def parse_scope(body: Optional[str]) -> tuple[Optional[str], Optional[str], str]:
    """Return (verdict, reason, state) for one ticket or issue body.

    state:
      ok           a verdict, and a reason where one is required
      absent       no Scope line at all -- the normal state of every issue predating this
      undecided    the line is still the placeholder
      no-reason    `di luar SoW` with no clause named: the one case where the reason IS
                   the deliverable, since the list exists to be handed to sales
      unparseable  a line that says something else entirely

    `dalam SoW` needs no reason. Routine in-scope work is most of the volume, and
    charging it a sentence each would buy nothing: the value is in the exceptions.
    """
    m = _SCOPE.search(body or "")
    if not m:
        return None, None, "absent"
    raw = m.group(1).strip()
    low = raw.lower()
    if not raw or SCOPE_PLACEHOLDER.lower() in low or (
            low.startswith("<") and low.endswith(">")):
        return None, None, "undecided"
    # Out is checked first: "di luar SoW" contains neither _IN_WORDS entry, but a
    # reason may well mention being in scope for something else.
    verdict = None
    for w in _OUT_WORDS:
        if low.startswith(w):
            verdict = OUT_OF_SOW
            break
    if verdict is None:
        for w in _IN_WORDS:
            if low.startswith(w):
                verdict = IN_SOW
                break
    if verdict is None:
        return None, raw, "unparseable"
    reason = raw.split("—", 1)[1].strip() if "—" in raw else (
        raw.split(" - ", 1)[1].strip() if " - " in raw else "")
    if verdict == OUT_OF_SOW and not reason:
        return verdict, None, "no-reason"
    return verdict, reason or None, "ok"


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 3 and w not in _STOPWORDS}


def _clauses(text: str) -> tuple[list, list, list]:
    """(in_scope, out_of_scope, sections) — clauses as (line_number, clause) pairs.

    Sections are classified by heading, not by content:

      before the first `##`    in scope — a SoW states what it covers before it
                               states what it does not
      `## Out of scope`        out of scope
      anything else            reference (SLA tables, customer responsibilities,
                               AWS's own terms) — read for neither verdict

    Plus any table row carrying ✅ anywhere in the document, as a safety net.

    That layout rule is a heuristic and will be wrong on a SoW laid out differently,
    which is a third reason this module returns candidates instead of verdicts. The
    sections list is returned so a wrong reading is visible rather than silent.

    The ✅ test alone is not enough: acme-retail's "Scope of work Trend Micro CloudOne
    Level-1 Support" table has no ticks and its title is a plain paragraph rather than
    a heading, so a ✅-only scan misses a whole contracted service — the exact section
    that was misread as excluded on 2026-10-07.
    """
    text = _blank_html_comments(text)
    in_scope: list[tuple[int, str]] = []
    out_scope: list[tuple[int, str]] = []
    sections: list[dict] = []
    bucket = "in"          # before the first ## heading
    sections.append({"heading": "(pembuka)", "line": 1, "bucket": "in"})
    for n, line in enumerate(text.splitlines(), 1):
        s_ = line.strip()
        if s_.startswith("## "):
            head = s_[3:].strip()
            bucket = ("out" if head.lower().startswith("out of scope")
                      else "ref")
            sections.append({"heading": head or "(tanpa judul)", "line": n,
                             "bucket": bucket})
            continue
        if not s_:
            continue
        is_item = (s_.startswith(("*", "-", "+")) or re.match(r"^\d+[.)]", s_)
                   or s_.startswith("|"))
        if bucket == "out":
            if is_item:
                out_scope.append((n, _clean(s_)))
        elif bucket == "in":
            if is_item:
                in_scope.append((n, _clean(s_)))
        elif "✅" in s_:
            # A tick outside the scope sections still marks something included.
            in_scope.append((n, _clean(s_)))
    return in_scope, out_scope, sections


def _blank_html_comments(text: str) -> str:
    """Blank out `<!-- ... -->` while KEEPING the line count, so line numbers still
    point at the document a reader opens.

    Found by the first live test on acme-retail, 2026-10-07: this SoW carries an import
    note in an HTML comment that itself lists the section names, including a bullet
    reading `- "## Out of scope" — yang eksplisit DI LUAR`. Those bullets ranked as the
    top two IN-SCOPE candidates for "install nginx" — a confident label on text saying
    the opposite, which is worse than returning nothing.
    """
    def _blank(m: "re.Match") -> str:
        return "\n" * m.group(0).count("\n")
    return re.sub(r"<!--.*?-->", _blank, text, flags=re.DOTALL)


def _clean(s: str) -> str:
    """Strip list and table punctuation so a clause reads as a sentence."""
    s = s.lstrip("*-+ ").strip()
    if s.startswith("|"):
        cells = [c.strip() for c in s.strip("|").split("|")]
        cells = [c for c in cells if c and not set(c) <= set(": -")]
        s = " — ".join(cells)
    return s.replace("\\", "").strip()


def scope_candidates(customer: str, activity: str, limit: int = 5) -> dict:
    """Clauses worth READING for this activity. Not a verdict.

    Both sides are always returned, deliberately. Reading only the out-of-scope list is
    exactly how this gets decided wrongly -- that list reads as absolute while other
    clauses quietly qualify it, and the overlap between "Patch Management ✅" and
    "Changes and troubleshoot on Operating System level" is a real contradiction in the
    acme-retail document, not something a ranking can resolve.

    Ranking is plain shared-word overlap. Deliberately dumb: anything cleverer would
    invite being trusted, and the whole point is that it must not be.
    """
    st = sow_status(customer)
    if not st.get("gated"):
        return {"customer": customer, "gated": False, "reason": st["reason"],
                "candidates": None}
    text = Path(st["sow_path"]).read_text(encoding="utf-8")
    q = _words(activity)
    if not q:
        return {"customer": customer, "gated": True, "sow": st["sow"],
                "error": f"activity {activity!r} tidak punya kata yang bisa dicocokkan"}
    in_scope, out_scope, sections = _clauses(text)

    best = 0

    def rank(pairs):
        nonlocal best
        scored = [(len(q & _words(c)), n, c) for n, c in pairs]
        scored = [x for x in scored if x[0] > 0]
        scored.sort(key=lambda x: (-x[0], x[1]))
        if scored:
            best = max(best, scored[0][0])
        return [{"line": n, "overlap": sc, "clause": c[:300]}
                for sc, n, c in scored[:limit]]

    ranked_in, ranked_out = rank(in_scope), rank(out_scope)
    out = {
        "customer": customer, "gated": True, "sow": st["sow"],
        "activity": activity,
        "in_scope_candidates": ranked_in,
        "out_of_scope_candidates": ranked_out,
        "sections_read": sections,
        "out_of_scope_total": len(out_scope),
        "not_a_verdict": (
            "Ini kandidat untuk DIBACA, bukan putusan. Baca kedua sisi — daftar "
            "out-of-scope terbaca absolut padahal sebagian dibatalkan klausa lain, "
            "dan dokumen ini tidak punya aturan presedensi. Yang memutuskan: manusia."),
        "how_to_record": (
            "Tulis di banner ticket: `> **Scope:** di luar SoW — <klausa>` atau "
            "`> **Scope:** dalam SoW`"),
    }
    # A single weak match is worse than none: it reads as "the tool looked and this is
    # what there is". Measured case — "upgrade windows server 2016 ke 2022" returns only
    # "Microsoft Windows domain integration" (one shared word, a different subject
    # entirely) while the two clauses that actually decide it, "Changes and troubleshoot
    # on Operating System level" and "Patch Management", share no word with the query at
    # all. Word overlap cannot reach them, so say so rather than imply coverage.
    if best <= 1:
        out["weak_match"] = True
        out["warning"] = (
            f"Pencocokan kata lemah (overlap tertinggi {best}) — kandidat di atas "
            f"mungkin tidak relevan dan yang relevan mungkin tidak muncul. Baca "
            f"sendiri daftar out-of-scope: {len(out_scope)} klausa, "
            f"{_section_range(sections, 'out')}. Bahasa kontrak dan bahasa tiket "
            f"sering tidak memakai satu kata pun yang sama.")
    return out


def _section_range(sections: list[dict], bucket: str) -> str:
    """Where to read a bucket in full, as "baris 129-151"."""
    for i, sec in enumerate(sections):
        if sec["bucket"] == bucket:
            end = sections[i + 1]["line"] - 1 if i + 1 < len(sections) else None
            return f"baris {sec['line']}" + (f"-{end}" if end else " ke bawah")
    return "tidak ada seksi out-of-scope yang terdeteksi"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def classify_issues(issues: list[dict]) -> dict:
    """Group issues by their recorded scope verdict. Pure, so it is testable."""
    out: dict[str, list] = {OUT_OF_SOW: [], IN_SOW: [],
                            "undecided": [], "absent": [], "needs_reason": []}
    for i in issues:
        verdict, reason, state = parse_scope(i.get("body"))
        row = {"number": i["number"], "title": i.get("title", ""),
               "state": i.get("state", "").lower(), "closedAt": i.get("closedAt")}
        if state == "ok":
            out[verdict].append({**row, "reason": reason} if verdict == OUT_OF_SOW else row)
        elif state == "no-reason":
            out["needs_reason"].append(row)
        elif state == "undecided":
            out["undecided"].append(row)
        else:
            out["absent"].append(row)
    return out


def report_out_of_sow(customer: str, period: Optional[str] = None,
                      state: str = "all") -> dict:
    """Activities recorded as outside the customer's SoW.

    customer: registry slug
    period:   "YYYY-MM" — filters on when the issue CLOSED, so a period necessarily
              excludes work still in flight
    state:    "all" (default), "closed" or "open"

    No work weight. The weight scale is internal capacity planning; the moment a
    `change-high x prod = 12` reaches a customer it becomes a billing unit to haggle
    over. What travels outward is the list and the count.
    """
    if period and not re.fullmatch(r"\d{4}-\d{2}", period):
        return {"error": f"period harus YYYY-MM, bukan {period!r}"}
    if state not in ("all", "closed", "open"):
        return {"error": f"state harus all/closed/open, bukan {state!r}"}

    st = sow_status(customer)
    r = _run(["gh", "issue", "list", "--repo", REPO,
              "--label", f"customer:{customer.lower()}", "--state", state,
              "--limit", "500", "--json", "number,title,body,state,closedAt"])
    if r.returncode != 0:
        return {"error": r.stderr.strip()}
    issues = json.loads(r.stdout or "[]")
    if period:
        issues = [i for i in issues if (i.get("closedAt") or "").startswith(period)]

    g = classify_issues(issues)
    out = {
        "customer": customer, "period": period or "semua waktu", "state": state,
        "gated": st.get("gated", False), "sow": st.get("sow"),
        "issues_scanned": len(issues),
        "out_of_sow": g[OUT_OF_SOW],
        "out_of_sow_count": len(g[OUT_OF_SOW]),
        "in_sow_count": len(g[IN_SOW]),
        "needs_reason": g["needs_reason"],
        "undecided": g["undecided"],
        "no_scope_line": len(g["absent"]),
    }
    decided = len(g[OUT_OF_SOW]) + len(g[IN_SOW])
    out["summary"] = (
        f"{len(g[OUT_OF_SOW])} di luar SoW · {len(g[IN_SOW])} dalam SoW · "
        f"{decided} dari {len(issues)} issue sudah diputuskan")
    if not st.get("gated"):
        out["warning"] = st["reason"]
    if g["absent"]:
        out["note"] = (
            f"{len(g['absent'])} issue tanpa baris Scope sama sekali — issue yang "
            "dibuat sebelum aturan ini. Tidak disentuh.")
    if g["needs_reason"]:
        out["action_needed"] = (
            f"{len(g['needs_reason'])} issue ditandai di luar SoW tanpa menyebut "
            "klausanya — tanpa itu daftarnya tidak bisa dipakai sales")
    return out
