# Issue body and comments

Summary of `docs/standards/ops-issue-format.md`. The standard wins on any
difference.

## The test

A PM opens the issue from the board. **The body alone** must answer:

1. Where does this stand?
2. Whose ball is it?
3. What is the next step?
4. When did it last move, and how long has it been stuck?
5. What is blocking it, if anything?

## Body: 5 blocks

| # | Block | Holds |
|---|---|---|
| 1 | Status banner | `> **Status:** … · **Bola di:** … · **Next:** …`, `**Update terakhir:**`, `**Bobot kerja:**` |
| 2 | `## Environment` | identifiers and minimal context; a `Dokumen` row for the MoP, tracker, KB |
| 3 | `## Masalah` | what happened or what was requested (2 to 3 lines) |
| 4 | `## Action items` | table `# / Action / PIC / Status`; each row links its evidence comment |
| 5 | `## Root cause` (incident) or `## Catatan & keputusan` (change) | only what stops someone doing the wrong thing |

The `Environment` table may also carry a `Dokumen` row (MoP, tracker, KB) and, at Done, a
`Docs Delta` row: `diperbarui: <files>` or `tidak ada perubahan`.

Row status words: `Done YYYY-MM-DD`, `In Progress`, `Pending`, `Blocker`;
dependencies after a dot: `Pending · blok #1`. No emoji. Do not add a
`## Referensi` block.

## Comments

Append-only, dated, evidence only. Heading: `## YYYY-MM-DD — FINDING`,
`ACTION`, `RESOLUTION` or `ARCHIVE`. Written by `issue_update_action_item`,
`issue_move_detail_to_comment` and `issue_rewrite_body`. A comment never holds the answer
the body should hold.

Notes use **Performed / Verification / Result** (usually 3–8 useful lines); blocked
items also name the dependency, PIC and next input. The tool adds the action number
and links completed action text to its evidence. Routine updates need no full-body
archive. See the standard's **Action checkpoint contract** for examples.

## Get body

What `issue_create` writes:

```
> **Status:** Open · **Bola di:** Example MSP · **Next:** tentukan owner, lalu analisa
> **Update terakhir:** <YYYY-MM-DD HH:MM> — issue dibuat
> **Bobot kerja:** TBD (diisi setelah analisa)

## Environment
| Item | Value |
|---|---|
| Customer | <slug> |
| Environment | <prod | non-prod | unknown> |
| Resource | <only when given> |
| Requester | <name, channel, date> |

## Masalah
<Symptom.>

**Dampak:** <Impact.>

## Action items
| # | Action | PIC | Status |
|---|--------|-----|--------|
| 1 | Analisa dan usulkan action item | Example MSP | Pending |

## Catatan & keputusan
<Evidence the reporter already has, or "Belum ada.">
```

Title: `[<slug>] <title>`. The Analyze stage replaces the placeholder row and the
weight.
