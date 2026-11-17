"""A one-page index of a customer's knowledge, built on request from front matter. Read-only.

Hand-written index files rot and collide in a repo many people write to. This builds the
index when it is asked for, from the front matter of each document, so there is nothing to
keep in step. A document without front matter still appears (title from its H1, type from
its folder) and is counted, so the gap is visible and shrinks as documents are touched.

Front matter (five fields, all optional, see docs/standards/ops-docs-schema.md):
  type: docs | kb | mop | incident | assessment | project | report | runbook
  summary: one sentence
  tags: [..]            applies_to: [..]
  verified: YYYY-MM-DD  (docs)       parent: <path of the runbook or MoP this builds on>
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from msops.tools.customers import load_customers

_ROOT = Path(__file__).resolve().parents[2]
_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
# folder -> type when the document does not say. Tickets are records, left out unless asked.
_FOLDER_TYPE = {"docs": "docs", "knowledge-base": "kb", "mop": "mop",
                "incident_report": "incident", "assessment": "assessment",
                "projects": "project", "reports": "report", "mom": "mom",
                "tickets": "ticket"}


def parse_front(text: str) -> dict:
    m = _FRONT.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _title(text: str, fallback: str) -> str:
    body = _FRONT.sub("", text, count=1)
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _summary(text: str) -> str:
    body = _FRONT.sub("", text, count=1)
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith(("#", "<!--", ">", "|", "-", "*", "```")):
            return s[:140]
    return ""


def entry(rel: str, text: str, folder_type: str) -> dict:
    fm = parse_front(text)
    return {
        "path": rel,
        "type": str(fm.get("type") or folder_type),
        "title": _title(text, Path(rel).stem),
        "summary": str(fm.get("summary") or _summary(text))[:100],
        "tags": [str(t) for t in (fm.get("tags") or [])],
        "applies_to": [str(t) for t in (fm.get("applies_to") or [])],
        "parent": str(fm.get("parent") or ""),
        "verified": str(fm.get("verified") or ""),
        "front_matter": bool(fm),
    }


def build_index(entries: list[dict], query: str = "", per_group: int = 8) -> dict:
    q = query.lower().strip()
    kept = [e for e in entries if not q or q in " ".join(
        [e["path"], e["title"], e["summary"], *e["tags"], *e["applies_to"]]).lower()]
    groups: dict[str, list[dict]] = {}
    for e in sorted(kept, key=lambda e: (e["type"], e["path"])):
        g = groups.setdefault(e["type"], [])
        if len(g) < per_group:
            # the group key already says the type; empty fields cost tokens and say nothing
            g.append({k: v for k, v in e.items()
                      if k not in ("type", "front_matter") and (v not in ("", [], False) or k == "path")})
    counts = {t: sum(1 for e in kept if e["type"] == t) for t in groups}
    return {
        "total": len(kept),
        "with_front_matter": sum(1 for e in kept if e["front_matter"]),
        "counts": counts,
        "truncated": {t: n - per_group for t, n in counts.items() if n > per_group},
        "groups": groups,
    }


def collect(root: Path, customer: str, include_tickets: bool = False) -> Optional[list[dict]]:
    match = next((c for c in load_customers(root)
                  if customer.lower() in {c.folder.lower(), c.name.lower()}), None)
    if match is None:
        return None
    base = root / match.folder
    out = []
    for sub, ftype in _FOLDER_TYPE.items():
        if sub == "tickets" and not include_tickets:
            continue
        d = base / sub
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.md")):
            if f.is_file() and "_templates" not in f.parts:
                out.append(entry(f.relative_to(root).as_posix(),
                                 f.read_text(encoding="utf-8", errors="ignore"), ftype))
    # Cross-customer runbooks are the usual MoP parents, so they belong in every index.
    rb = root / "kb" / "runbooks"
    if rb.is_dir():
        for f in sorted(rb.rglob("*.md")):
            out.append(entry(f.relative_to(root).as_posix(),
                             f.read_text(encoding="utf-8", errors="ignore"), "runbook"))
    return out


def doc_index(customer: str, query: str = "", include_tickets: bool = False,
              per_group: int = 8, root: Path = _ROOT) -> dict:
    entries = collect(root, customer, include_tickets)
    if entries is None:
        return {"error": f"customer {customer!r} tidak dikenal — pakai get_customer"}
    return {"customer": customer, **build_index(entries, query, per_group)}
