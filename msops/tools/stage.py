"""Where an issue stands in the flow, and the one next step, computed from the issue itself.

The flow is Get, Analyze, Ship, Done (skill `ops-issue`). A step skipped is the usual way an
issue goes wrong: an item worked before the weight was set, a weight typed by hand instead of
classified. Remembering the flow is what fails, so the engine states it instead: every writer
and `issue_next` read this one function, and the banner carries the answer as a `Tahap` line
and a `Next` that names the command to run.

Rules, first match wins:

  closed, or banner Resolved   Done    nothing left
  no assignee                  Get     issue_analyze with login (issue_assign if rows exist)
  Bobot kerja TBD or absent    Analyze issue_analyze (issue_classify if rows exist)
  only the placeholder row     Analyze issue_analyze
  every row Done               Done    verify, customer reply, Docs Delta, issue_resolve
  otherwise                    Ship    the next open row (what the banner already said)

Ship and the all-rows-Done case keep the `Next` / `Bola di` the row-driven writer computed,
so this module only dictates them while the issue is still in Get or Analyze.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from msops.tools import banner

TOTAL = 4
ALL_DONE_NEXT = "verifikasi, balasan customer, Docs Delta, lalu issue_resolve"

_WEIGHT_LINE = re.compile(r"\*\*Bobot kerja:\*\*\s*(.*)")
_PLACEHOLDER = re.compile(r"analisa dan usulkan action item", re.IGNORECASE)


@dataclass(frozen=True)
class Stage:
    name: str
    n: int
    next: str
    bola: str
    # True while this module dictates Next / Bola di (Get and Analyze). In Ship the
    # next open row dictates them, which `issue_write` already writes.
    owns_next: bool = False

    @property
    def label(self) -> str:
        return f"{self.name} ({self.n} dari {TOTAL})"


def _cmd(name: str, number: Optional[int], args: str) -> str:
    # No angle brackets anywhere: GitHub renders `<login>` as an HTML tag and hides it.
    return f"{name}({number}, {args})" if number else name


def _banner_status(body: str) -> str:
    m = banner.STATUS.search(body)
    return m.group(2).strip().lower() if m else ""


def _weight_is_set(body: str) -> bool:
    m = _WEIGHT_LINE.search(body)
    if not m:
        return False
    value = m.group(1).strip()
    return bool(value) and not value.upper().startswith("TBD")


def weight_tbd(body: str) -> bool:
    """True when the `Bobot kerja` line exists but was never classified (`TBD`).

    The gate keys on this and not on an absent line: about 250 older issues have no
    weight line at all, and blocking their work would stop issues already under way.
    """
    m = _WEIGHT_LINE.search(body)
    return bool(m) and (not m.group(1).strip() or m.group(1).strip().upper().startswith("TBD"))


def weight_line(body: str) -> Optional[str]:
    """The `Bobot kerja` banner line as written, or None."""
    m = re.search(r"^>\s*\*\*Bobot kerja:\*\*.*$", body, re.MULTILINE)
    return m.group(0).strip() if m else None


def stage_of(body: str, assignees: list, state: str = "OPEN",
             number: Optional[int] = None, needs_scope: bool = False) -> Stage:
    """The stage of one issue. `number` is None while the issue does not exist yet."""
    # Imported here: issue_write imports this module to stamp the banner.
    from msops.tools.action_status import is_done
    from msops.tools.issue_write import TableError, _next_open, _plain_action, parse_action_items

    if (state or "").upper() == "CLOSED" or _banner_status(body).startswith(("resolved", "closed")):
        return Stage("Done", TOTAL, "—", "—")
    try:
        table = parse_action_items(body)
    except TableError:
        table = None
    rows = table["rows"] if table else {}
    placeholder_only = bool(rows) and all(_PLACEHOLDER.search(r["cells"][1]) for r in rows.values())
    real_rows = bool(rows) and not placeholder_only
    weighted = _weight_is_set(body)
    # Get and Analyze are one call (issue_analyze) while the table is still the intake
    # placeholder. Once real rows exist, issue_analyze would refuse to replace them, so
    # the missing piece is named on its own: the owner, or the classification.
    scope = ", scope" if needs_scope else ""
    if table is None:
        # An older body with no action-items table (47 open acme-retail issues on
        # 2026-10-15): issue_analyze would refuse it, so the first step is the reshape.
        if not assignees:
            return Stage("Get", 1, "tentukan owner dengan " + _cmd("issue_assign", number, "login"),
                         "Example MSP", owns_next=True)
        if weighted:
            return Stage("Ship", 3, "perbaiki tabel Action items dengan "
                         + _cmd("issue_rewrite_body", number, "body"), "Example MSP")
        return Stage("Analyze", 2, "rapikan body ke format 5 blok dengan "
                     + _cmd("issue_rewrite_body", number, "body") + ", lalu issue_classify",
                     "Example MSP", owns_next=True)
    if not assignees:
        if real_rows:
            return Stage("Get", 1, "tentukan owner dengan " + _cmd("issue_assign", number, "login"),
                         "Example MSP", owns_next=True)
        return Stage("Get", 1, "tentukan owner dan analisa dengan "
                     + _cmd("issue_analyze", number, f"type, env{scope}, actions, login"),
                     "Example MSP", owns_next=True)
    if not weighted and real_rows:
        return Stage("Analyze", 2, "klasifikasi kerja dengan "
                     + _cmd("issue_classify", number, f"type, env{scope}"), "Example MSP", owns_next=True)
    if not weighted or placeholder_only:
        return Stage("Analyze", 2, "analisa dengan "
                     + _cmd("issue_analyze", number, f"type, env{scope}, actions"),
                     "Example MSP", owns_next=True)
    nxt = _next_open(table)
    if nxt is None:
        return Stage("Done", TOTAL, ALL_DONE_NEXT, "Example MSP")
    pic = nxt["cells"][table["pic_col"]] if table["pic_col"] is not None else "Example MSP"
    return Stage("Ship", 3, _plain_action(nxt["cells"][1]), pic or "Example MSP")


def stage_for_issue(iss: dict, body: Optional[str] = None) -> Stage:
    """`stage_of` for an issue dict as `gh issue view --json` returns it."""
    labels = iss.get("labels") or []
    customer = next((l["name"].split(":", 1)[1] for l in labels
                     if isinstance(l, dict) and l.get("name", "").startswith("customer:")), "")
    needs_scope = False
    if customer:
        try:
            from msops.tools.scope import has_sow
            needs_scope = has_sow(customer)
        except Exception:  # noqa: BLE001 - a missing manifest must not hide the stage
            needs_scope = False
    return stage_of(iss.get("body") or "" if body is None else body,
                    iss.get("assignees") or [], iss.get("state") or "OPEN",
                    iss.get("number"), needs_scope)


def apply(body: str, st: Stage) -> str:
    """Write the `Tahap` line, and `Next` / `Bola di` while the stage owns them.

    A body without a status banner (older issues) is returned unchanged: the banner is
    what this edits, and inventing one here would hide the issue's real shape from audit.
    """
    lines = body.splitlines()
    idx = next((i for i, l in enumerate(lines[:8])
                if l.startswith(">") and "**Status:**" in l), None)
    if idx is None:
        return body
    if st.owns_next:
        l = lines[idx]
        l = banner.BOLA.sub(lambda m: m.group(1) + st.bola + " ", l, count=1)
        l = banner.NEXT.sub(lambda m: m.group(1) + st.next, l, count=1)
        lines[idx] = re.sub(r"\s+·\s*$", "", l.rstrip())
    tahap = f"> **Tahap:** {st.label}"
    for i, l in enumerate(lines[:8]):
        if banner.TAHAP.match(l):
            lines[i] = tahap
            break
    else:
        lines.insert(idx + 1, tahap)
    return "\n".join(lines)


def next_for(number: int) -> dict:
    """What `issue_next` returns: stage, next step and who holds it, read live from GitHub."""
    from msops.tools.integrations import get_issue
    iss = get_issue(number)
    if "error" in iss:
        return {"error": iss["error"]}
    st = stage_for_issue(iss)
    return {"issue": number, "title": iss.get("title"), "url": iss.get("url"),
            "state": iss.get("state"), "tahap": st.label, "stage": st.name,
            "next": st.next, "bola_di": st.bola,
            "assignees": [a.get("login") for a in iss.get("assignees") or []]}
