"""The status banner at the top of an issue body: the patterns every writer shares.

`issue_write`, `issue_resolve` and `stage` each edit the same few lines (`Status`,
`Bola di`, `Next`, `Update terakhir`, `Tahap`). Each used to carry its own copy of the
regexes, and a copy that drifts is how a body and its banner end up disagreeing. One
definition here; the writers import it.

Contract: docs/standards/ops-issue-format.md
"""
from __future__ import annotations
import re

STATUS = re.compile(r"^(>\s*\*\*Status:\*\*\s*)([^·\n]*)", re.MULTILINE)
BOLA = re.compile(r"(\*\*Bola di:\*\*\s*)([^·\n]*)")
NEXT = re.compile(r"(\*\*Next:\*\*\s*)([^·\n]*)")
UPDATED = re.compile(r"^>\s*\*\*Update terakhir:\*\*.*$", re.MULTILINE)
TAHAP = re.compile(r"^>\s*\*\*Tahap:\*\*.*$")
