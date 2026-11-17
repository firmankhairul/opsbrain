"""Action-item status words, shared by the writer, the auditor and the tracker.

Status is plain text since 2026-10-08: `Done 2026-10-08` · `In Progress` · `Pending`
· `Blocker`. Bodies written before that carry the emoji forms (✅ Done, ⬜ Pending, …);
those are still read correctly, so no issue has to be migrated.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import re

STATES: dict[str, str] = {
    "done": "Done",
    "in_progress": "In Progress",
    "blocked": "Blocker",
    "pending": "Pending",
    # Waiting for an approver, as opposed to blocked by access or another team.
    "pending_approval": "Pending Approval",
}

# `✅` covers legacy rows; the word must open the cell so "Not done" or a note that
# merely mentions "done" never closes an item.
_DONE = re.compile(r"✅|^\W*done\b", re.IGNORECASE)


def is_done(status_cell: str) -> bool:
    return bool(_DONE.search(status_cell.strip()))
