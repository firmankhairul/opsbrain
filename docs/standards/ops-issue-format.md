# Ops Issue Format & Work Weight

> **Cross-agent doc.** Applies to every agent working in this repo (Kiro, Codex,
> Claude, Gemini, OpenCode), not just one. Referenced from `ops-rules.md` and
> mirrored into `.kiro/steering/ops-issue-format.md`. Keep this file as the single
> source of truth; edit here, not the mirror.

Defines how a GitHub Issue in `your-org/ms-ops` is written and maintained, and how
operational work is weighted. Applies to **all customers**.

---

## Why this exists

Issues became hard to read because the **body was written once and then frozen**,
while every development piled up in comments. To learn the current state a reader had
to walk the whole thread, and the body often **contradicted** the comments.

Observed before this standard (2026-09-29):

| Issue | Body said | Reality |
|---|---|---|
| #316 | `Status: Open`, `Scheduled: Rabu`, 15 action items `[ ]`, instance `i-046a453c...` | Issue CLOSED, upgrade done 23 Sep, that instance already terminated |
| #343 | Root cause = RAM exhausted by hung sessions | The 29 Sep incident root cause was **RDS licensing** — buried in the 4th comment |

The real hazard is not untidiness: a reader (human or AI agent) who trusts the body
gets a **wrong answer** and acts on it.

## How an issue starts (since 2026-10)

An issue is **born on GitHub** with `issue_create` and worked through Get, Analyze, Ship, Done
(skill `ops-issue`, walkthrough in `docs/guides/workflow.md`). It starts with `Bobot kerja: TBD`
and a single placeholder action row on purpose: the action items and the weight come out of the
analysis, not out of the report. `issue_audit_format` flags a `TBD` weight until Analyze sets it.
A ticket file is no longer the starting point (the `ticket_file_*` tools remain for the existing
files). The `Environment` table may carry a `Dokumen` row (MoP, runbook, KB) and, at Done, a
`Docs Delta` row (`diperbarui: <files>` or `tidak ada perubahan`). A MoP exists only when
`ops-rules.md` rule 9 requires one.

**Tahap and Next are computed, not typed (since 2026-10-15).** The banner carries a
`> **Tahap:** <Get|Analyze|Ship|Done> (n dari 4)` line under the Status line. The tools
compute it from the issue (owner, `Bobot kerja`, action-items table) with one function, the
same one `issue_next(N)` answers from; while the issue is in Get or Analyze, `Next` names
the command to run (`issue_analyze(...)`, `issue_assign(...)`, `issue_classify(...)` or
`issue_rewrite_body(...)`). `in_progress` and `done` are refused while `Bobot kerja` is
`TBD`, and a `Bobot kerja` line that exists is changed only by `issue_classify` or
`issue_analyze`; `force=True` passes either gate and is recorded.

**Banner status is derived, and Resolved is explicit.** `issue_update_action_item` sets
the banner Status from the status of the call it just recorded: `In Progress` for
`in_progress` and `done`, and also when every row is done but the work is not
(verification, customer reply, Docs Delta still follow); `Pending Approval` for
`pending_approval` (waiting for an approver); `Escalated` for `blocked` (waiting on access
or another team). Work Example MSP finished that now waits for an approver is two rows, the work
`Done` and a separate approval row `Pending Approval` with the PIC who decides, so the
banner keeps saying what the issue waits for. The board's Status, Weight and Segment are
mirrored from the issue every time a tool writes it. `Resolved` is written only by
`issue_resolve`, together with the `Docs Delta` row and the RESOLUTION comment that names
who decided. An issue may be filed and analysed without an assignee; it cannot be marked
done or resolved without one.

**`Parent` is for projects and existing umbrellas only.** A change that comes out of an issue
is a new issue with `Related: #N`, not a sub-issue. The native parent relation is reserved for
a project umbrella and its deliverables (SOP: Pekerjaan biasa vs proyek) and for the batch
umbrellas that already exist (#79).

Root cause of the staleness: the **source ticket file is not maintained** after
creation, and `ticket_file_sync_to_issue` faithfully copies it. The sync is not at fault.

---

## Core rule

| Place | Purpose | Nature |
|---|---|---|
| **Issue body** | The state **NOW** — single source of truth | Targeted updates as state changes |
| **Comment** | Dated historical trail, detail, evidence | Append-only, never deleted |
| **`.md` file in repo** | Long standalone documents (MoP, IR, KB, assessment) | Versioned by git |

Quick test: if the content is *"what happened, when"* → comment. If it is *"a document
that reads on its own without the issue"* → `.md` file, linked from the body.

### Derived rules (mandatory)

1. **Preserve substantive history.** Before removing unique evidence, identifiers or
   decisions from the body, move that material into a linked dated comment. Routine
   status/date/next-action updates and evidence links need no full-body archive: the
   action comment records the transition. Reserve `issue_rewrite_body` (which archives
   the old body) for structural cleanup or substantive replacement. GitHub tooling
   returns only the current body, so preserve removed facts before replacement.
2. **Identifiers must survive IN THE ISSUE — in the body only if a reader needs them to
   act now.** Verified 2026-10-01: GitHub issue search indexes comments, so an id in an
   archive or inventory comment is just as findable (`267af416` exists only in #154's
   archive comment and search returns #154 for it). The earlier wording — "identifiers
   stay in the body" — was read strictly and did damage: it forced 29 ids into #154's
   Environment table, making it 31% of a body that is supposed to be a summary.
   So: the active resource and anything named by a pending action item belong in
   `## Environment`; terminated instances, deleted volumes, security groups and other
   history go to a comment, linked from the action item that needs them. #343 was found
   because `i-058072f88eb6534f0` was *in the issue* — the body was merely where it
   happened to be.
3. **Drop frozen metadata.** `Priority`, `Scheduled`, `Requester` that nobody updates
   are worse than absent — they mislead. Rely on labels and the project board.
4. **State corrections explicitly.** When a finding changes, write
   *"previously suspected X → corrected to Y (see comment)"* **and** update the body.
   This is what #343 lacked.
5. **Environment may stay static — EXCEPT when the resource changes.** In #316 the old
   instance was terminated and replaced by `i-0a7c36679ff2426e1`; the table must be
   updated, while **keeping the old ID** so historical searches still hit.
6. **A new incident is a new issue**, not a comment on a closed issue with a different
   root cause. Link it with "Recurrence of #xxx". One issue = one story.

### Writing conventions

**Action checkpoint contract.** The body must let another engineer continue without
reading the entire thread: use `verb + target + completion condition` for each action,
an accountable PIC and current status. Keep the four existing columns; the **Action
cell** links to the evidence comment on completion (as the tool already does).

Pass a short note to `issue_update_action_item`; it adds the date, action number/title
and machine marker. Use these fields; omit empty optional fields:

```markdown
**Performed:** Deleted taskmgmtdbprd after the verified final backup.
**Verification:** DBInstanceNotFound at 14:48 WIB; final snapshot available/encrypted.
**Result:** Done.
```

For `in_progress`, state the concrete finding and next check. For `blocked` or
`pending_approval`, state the dependency, responsible party and exact input needed.
For `done`, provide the observed result and timestamp or evidence link, not just
“completed”. Default to 3–8 useful lines; inventories/output belong in a linked
document or dedicated detail comment. State approval source once and refer back to it.
One checkpoint records one meaningful change, not every command or routine read.
Current tooling updates one row per call; keep each note specific to that row.

At close-out, use one short resolution with outcome, actual communication evidence,
Docs Delta and closure decision source. Link existing evidence instead of repeating
backup registers, full configuration or the issue body. The recipient/channel must be
truthful; operator-directed closure is distinct from a customer email being sent.

- **Comment heading:** `## YYYY-MM-DD — FINDING` / `ACTION` / `RESOLUTION` / `ARCHIVE`
- **Status (plain text, no emoji):** `Done YYYY-MM-DD` · `In Progress` · `Pending` ·
  `Blocker`. Dependencies ride after the word: `Pending · blok #2`. Since 2026-10-08;
  older bodies with ✅/⬜/🔄/🔴 are still read correctly by the tools, so there is no
  need to rewrite them — they convert the next time `issue_update_action_item` touches a row.
- **No emoji in issue titles, bodies or comments.** Status, severity and scope are
  words. An emoji carries no information a word does not, and it breaks search,
  copy-paste into customer email, and the docx/PDF export.
- **Voice: we are Example MSP.** Write as Example MSP, not as a person — "Example MSP menjalankan backup AMI",
  PIC `Example MSP` for anything our team owns. Individual names only for the customer side
  (e.g. `Pak Yoga`).
- **"Scope" / "SoW" means the contract, nothing else.** The words are reserved for the
  `Scope` banner verdict, because readers and GitHub search take "di luar scope" as
  "outside the SoW". For anything else, say what is meant: `tanggung jawab Tim App`,
  `bukan bagian task ini`, `ditunda (parked)`, `bukan urusan AWS`. On 2026-10-08 about
  15 issues read as out-of-SoW for this reason alone.
- **The Scope verdict judges Example MSP's own work.** Parts done by Tim App or the customer
  never make an issue out-of-SoW — an out-of-scope clause that explains *why Tim App
  does it* is not a reason to mark Example MSP's part. #384 was marked out-of-SoW on the
  runtime-install clause while Example MSP's part (new instance + AWS/TrendMicro agents) is
  contracted; corrected to in-SoW.
- **PIC:** `Example MSP` / `Tim App` / `PIC Customer`
  (acme-retail uses `Pak Yoga` for that third slot — all global/Wintel/DNS
  communication goes through him)
- **Register, not length.** The body is a summary, so 40 lines of command output is
  worse than 60 lines of summary. Length is a symptom; what matters is that execution
  detail — command output, manifests, raw inventories, step-by-step procedures — lives
  in a comment or a linked `.md` file, never in the body.
- Unavoidably long content in the body → wrap in `<details><summary>…</summary>`

---

## The test the body must pass

The reader is a PM in a sync-up meeting, clicking each issue from the board. **The body
alone must be enough** — no scrolling the comments. Concretely it has to answer five
questions:

1. Where does this stand?
2. Whose ball is it?
3. What is the next step?
4. When did it last move — and how long has it been stuck?
5. What is blocking it, if anything?

That is a stronger requirement than "keep it short": the body must be *complete for
deciding*, not merely brief. Comments hold **evidence** — command output, execution
records, archives — the things you only open when you need to dig. They never hold the
answer itself.

Measured on 2026-09-30: **12 of 66** open acme-retail issues passed all five; **52
answered none**. That is the gap this standard exists to close.

## Body structure: 5 blocks

```
1. Status banner        → where it stands, whose ball, next step, days idle, weight
2. Environment          → identifiers + minimal technical context + standing documents
3. Masalah / Problem    → what happened or what was requested
4. Action items (table) → progress map: what, who, how far — each row may link its evidence
5. Root cause / Notes & decisions → things that are NOT tasks
```

Two blocks were dropped, both for the same reason: **nothing maintains them, so they go
stale.**

- A 7th block, "Kondisi sekarang", duplicated the action-items table.
- **`## Referensi` (2026-09-30).** It was 18% of #316's body and answered none of the
  five questions. A hand-maintained link list is the first thing to rot. Evidence now
  attaches to the action item it documents, written there by `issue_update_action_item` from
  the comment it just posted — so the link is a by-product of the work instead of a
  discipline. Standing documents (MoP, tracker, KB) move to a `Dokumen` row in
  `## Environment`, which is already the facts table. A parent umbrella needs no line at
  all: it is a native sub-issue relation and shows on the board as `Parent issue`.

Duplicated information means two places to update, which reproduces the contradiction
this standard exists to prevent. In #316 the parent `#79` appeared **three times** —
in the Masalah prose, in Referensi, and as the native relation.

Block 5 is titled **Root cause** for incidents (people look for it by that name) and
**Notes & decisions** for changes.

**It holds only what stops someone doing the wrong thing.** That is the test; history
goes to a comment. #154's block was six bullets until three of them turned out to be
narrative ("rename hostname was not needed", "DeleteOnTermination found on the day",
"cutover was held on 14 August") — true, already implied by the action items, and not
preventing any mistake. The three that stayed each block a specific wrong action:
adding `301,302` to a health-check matcher that will not help, deleting a rollback AMI
during housekeeping, and deleting another server's volumes under this issue's name.

It carries what does not fit the table and does not belong in the banner: external
blockers and why, current impact, corrected plans, or warnings for the future. Example from #316: *"rollback AMI must not be deleted"* —
precisely because it is not an action item, it would otherwise be lost and the AMI
could be removed during the next housekeeping.

### Skeleton — Incident

```markdown
> **Status:** Open · **Bola di:** Example MSP · **Next:** <next step>
> **Tahap:** <Get|Analyze|Ship|Done> (<n> dari 4) — written by the tools
> **Update terakhir:** YYYY-MM-DD — <one line on what changed> · **<N> hari tanpa gerak**
> **Bobot kerja:** <P4=3 · P3=5 · P2=8 · P1=13> × <prod 1,5 / non-prod 1> <+3 if cross-layer or rework>
> **Scope:** <dalam SoW | di luar SoW — clause> (only when customer.yaml names a `sow:`)

## Environment

| Item | Value |
|---|---|
| Instance | `i-xxxxxxxx` (name) |
| cmdbid / IP | |
| OS / Type | |
| Account / Region | |
| Dokumen | [ticket](<path>) · [IR](<path>) · [KB](<path>) |

## Masalah

<2–3 lines: reported symptom, since when, user impact.>

## Action items

| # | Action | PIC | Status |
|---|--------|-----|--------|
| 1 | <action, wrapped in a link to its evidence comment once there is one> | Example MSP | Pending |

## Root cause

<Current version only. If it changed, say so explicitly:
"previously suspected X → corrected to Y (see comment <link>)".>

## Catatan

<Things that are NOT action items but must be read: external blocker and why,
current impact, warnings (e.g. "the fix is temporary, it will recur"), and how many
attempts an item took when that is what drives the rework adder.
Delete this block if empty.>
```

### Skeleton — Change

```markdown
> **Status:** Open · **Bola di:** <Example MSP / Tim App / PIC Customer> · **Next:** <next step>
> **Tahap:** <Get|Analyze|Ship|Done> (<n> dari 4) — written by the tools
> **Update terakhir:** YYYY-MM-DD — <one line on what changed> · **<N> hari tanpa gerak**
> **Bobot kerja:** <change-low=3 · change-high=8> × <prod 1,5 / non-prod 1> <+3 if rework outside normal procedure>
> **Scope:** <dalam SoW | di luar SoW — clause> (only when customer.yaml names a `sow:`)

## Environment

| Item | Value |
|---|---|
| Instance | `i-xxxxxxxx` (name) |
| cmdbid / IP / Hostname | |
| OS / Type | |
| AMI / snapshot rollback | |
| Dokumen | [MoP](<path>) · [tracker](<path>) · [KB](<path>) |

## Masalah

<2–3 lines: what was requested + the end state. Do NOT name the umbrella here —
`**Parent**: #N` makes it a native relation, and repeating it in prose is the
duplication this standard exists to prevent.>

## Action items

| # | Action | PIC | Status |
|---|--------|-----|--------|
| 1 | <action, wrapped in a link to its evidence comment once there is one> | Example MSP | Pending |
| 2 | <depends on another row> | Example MSP | Pending · blok #1 |

## Catatan & keputusan

<Key decisions and corrected plans ("original plan X → corrected to Y, see comment"),
active blockers, warnings for the future (e.g. "rollback AMI must not be deleted"),
and how many attempts an item took when that is what drives the rework adder.>
```

**Optional meta line** — for work that belongs to a batch:

```
**Parent**: #79
```

`ticket_file_sync_to_issue` reads this and registers the issue as a **native
sub-issue** of that umbrella, so it appears in the umbrella's sub-issue list and
progress count. Writing "Sub-issue of #79" in prose does **not** create the
relation — GitHub treats that as a mention. The line may sit on its own or after
a `·` separator on the meta line. The convention predates the tooling: 8
acme-retail tickets already carried it by hand.

### How the rules are actually enforced

A rule in a document is a wish. Two cases from this repo settle it: `## Referensi` was
mandated by this standard and was the first block to rot, and `update_ticket_status` was
documented as refreshing the banner while it never touched the header — which is the
mechanism behind every stale body in #316. So anything that matters is enforced by code.

| Layer | What it refuses | Where |
|---|---|---|
| **Analyze (issue path)** | `issue_analyze` / `issue_classify` compute `Bobot kerja` only when told `env` ("prod"/"non-prod"). It is never inferred: naming answers for 22% of 188 existing tickets, so inference would default silently on four tickets out of five | `issue_classify.classify_issue` |
| **Creation (ticket-file path)** | `ticket_file_sync_to_issue` refuses to create an issue whose action-items table is still the empty placeholder row, or whose `Bobot kerja` is unfilled. It also refuses an undecided `Scope` — but only for a customer whose customer.yaml names a `sow:`, so it blocks nothing for the other 46. Those are the things a scaffold cannot supply and a reader cannot do without. `force=True` overrides and says so | `integrations._creation_blockers` |
| **Commit** | Nothing. CI *reports* a ticket dated ≥ `TICKET_RULES_FROM` (2026-10-01) with no banner, no numeric weight, a placeholder action row, or a `## Referensi` — informational, never failing. Dated because 188 legacy tickets predate the standard and backfilling would mean guessing 188 weights | `scripts/check_repo_hygiene.py` |
| **After the fact** | `issue_audit_format` reports everything else — contradictions, open work that lives only in a comment, the five PM questions, idle days, execution detail in the body | read-only, never refuses |

**The commit layer is deliberately not a gate.** It was one, for four days, and it
failed CI seven times running on a hand-written acme-retail incident ticket whose banner was
correct and which simply had no weight line. That contradicted the rule already written
in `repo-hygiene.yml`: content debt is informational, structural rot is the hard gate.
Blocking took the checks that do matter — secrets, slugs, blob size — down with it, and
seven red notifications in a row teach people to ignore red. An unfilled weight is
content debt. It is reported and stays visible in the log.

The gates stop at these fields on purpose. Everything a human must judge — what the action
items are, what belongs in `## Masalah`, which notes prevent a wrong action — is reported
by the audit, not refused, because a script cannot make that call and blocking on it
would just teach people to write filler.

### GitHub issue templates are deliberately NOT used

`.github/ISSUE_TEMPLATE/` only applies to the web "New issue" chooser. Issues in this
repo are created by agents through `gh issue create --body` / the REST API, both of
which **bypass templates entirely**. Adding template files would therefore have no
effect on the actual flow. The skeletons above are the template.

---

## Scope: in-SoW or out-of-SoW

Activities outside a customer's Scope of Work get done anyway — refusing is rarely an
option — and until 2026-10-07 nothing recorded that they were outside. The customer then
reasonably assumes they were included all along, and at renewal there is no evidence to
price against.

One banner line carries it, in the ticket and in the issue body derived from it:

```markdown
> **Scope:** dalam SoW
> **Scope:** di luar SoW — out-of-scope #9 "Changes and troubleshoot on OS level"
```

`dalam SoW` needs no clause. `di luar SoW` **must** name one: the clause is the whole
deliverable, since the list exists to be handed to sales at renewal, and "we did extra
work, trust us" is not evidence.

**Two labels, never one.** `scope:in-sow` and `scope:out-of-sow`. With only the second,
an unlabelled issue cannot be told apart from one nobody has looked at — and at the
start that is nearly every issue. Undecided has to be a state you can count.

### Gated per customer, by a field and not by a file

The switch is `sow:` in `customer.yaml`:

```yaml
sow: contract/SOW-Managed-Service-acme-retail-2025-06-03.md
```

Present → every issue for that customer must state a verdict. Absent → the line is not
even scaffolded, because there would be no document to resolve it against. Of 47
customers, exactly the ones someone switched on.

It is the **field**, never the presence of a SoW file in the folder. Three customers
already have SoW documents sitting in the repo and `acme-retail` has four of them
(Migration and Remote Support, each in two languages), so "which SoW" is a real question
there that filename detection would answer by guessing. A `sow:` naming a file that does
not exist is reported by `sow_status`, not left as a gate sitting silently inert.

### The tool does not decide

`scope_candidates(customer, activity)` returns clauses **to read**, from both sides of
the contract, ranked by plain shared-word overlap. It renders no verdict, and that is
not caution for its own sake. Measured on 2026-10-07 against the acme-retail SoW with
the full text open:

- a keyword tally over it returned **3 false positives in 4 sampled cases** — CWAgent,
  IIS and K8S matched technology *names*, not activities
- two clauses were read **backwards outright**: TrendMicro appeared excluded as a "Non
  AWS Product" while in fact having its own scope section with its own 8x5 coverage, and
  "Create a New Environment" read as an absolute bar while a separate line grants a
  quota of **60 resources a year**

Both sides are always returned because reading only the out-of-scope list is exactly how
this is decided wrongly. That list reads as absolute while other clauses quietly qualify
it, and the document has no precedence rule — `Patch Management ✅ by Request` against
`Changes and troubleshoot on Operating System level` is a genuine contradiction no
ranking can resolve.

When the best word overlap is ≤ 1 the result carries `weak_match` and says where to read
the list in full. A single weak candidate reads as "the tool looked, and this is what
there is". The measured case: `upgrade windows server 2016 ke 2022` matches only
*"Microsoft Windows (a third party solution) domain integration"* — one shared word, a
different subject — while the two clauses that actually decide it share no word with the
query at all. Contract language and ticket language routinely have no word in common.

So the same rule as `env`, `priority` and `due`: **ask, never guess.** A placeholder is
an honest failure; a guessed verdict is a silent error with a customer on the other end.

### No work weight leaves the building

`report_out_of_sow` carries the list and the count, never `Bobot kerja`. The weight scale
is internal capacity planning; the moment `change-high × prod = 12` reaches a customer it
becomes a billing unit to haggle over — "why is this 12 and not 8?". Its value is in
planning, not in negotiation.

## Work weight

**Principle: weight belongs to the work, not to the person's clock.** It is assigned at
intake, before knowing who will do it — which removes the dependency on engineer skill.

Wall-clock duration is **not** used as the weight because:

- It is dominated by waiting, not working. Volume cleanup in #330–#335 sat for days
  waiting on customer approval; #315 was blocked on a domain secure channel — zero Example MSP
  effort in both.
- The incentive inverts: finishing in 20 minutes scores low, fumbling for three days
  scores high.

### Base weight

| Work type | Weight |
|---|---|
| `check` — status check, monitoring, routine report | 1 |
| KB entry / documentation | 2 |
| `change-low` — add/update/restart/config | 3 |
| Incident P4 | 3 |
| Incident P3 | 5 |
| Assessment / standalone analysis | 5 |
| `change-high` — migration, OS upgrade, cluster | 8 |
| Incident P2 | 8 |
| Incident P1 | 13 |

Documentation carries weight not because it is heavy, but so there is an incentive to
write KB entries at all.

**What the tooling computes, and what it refuses to guess.** `issue_analyze` and `issue_classify`
derive the weight from the task type plus two values the caller supplies:

| Needs | Why it is not inferred |
|---|---|
| `env` — "prod" / "non-prod" | Measured across 188 ticket files: naming identifies production in 19, non-production in 17, and **answers for neither in 148 (78%)**. Inference would default silently on four tickets out of five. |
| `priority` — "P1".."P4", incidents only | P1 is worth four times P4. Criteria are in **Incident severity** below; the label vocabulary is `P1 Critical · P2 High · P3 Medium · P4 Low` and nothing else — `P2 — Significant` and `P2 — Security` both appear in older reports and are not to be used, since `Security` is a kind of incident rather than a level. The same value sets the incident report's severity, so the two cannot disagree. |

Without them the line stays `<n>`, which parses as nothing — and
`ticket_file_sync_to_issue` then **refuses to create the issue**, naming the missing
parameter. Filling only the base weight would be worse than the placeholder: the
aggregation regex matches a digit, so an unmultiplied 8 on a production change reports
12 as 8 — a 33% undercount with nothing flagging it.

Rounding is half **up**, not Python's banker's rounding: example #27 below is
`change-low 3 × 1,5 + 3 = 8`, i.e. 4.5 → 5, where `round(4.5)` returns 4 and would
give 7.

### Incident severity — P1 to P4

Labels come from the `ms-ops` skill: **P1 Critical · P2 High · P3 Medium · P4 Low**.
The criteria below were adopted 2026-10-06, derived from the 15 incident reports in this
repo that recorded a severity rather than copied from ITIL.

| | Deciding question | Applies when |
|---|---|---|
**P1** | Has the customer's work **stopped**, or is data already **out or encrypted**? | production service fully down · business operations halted · data confirmed exfiltrated · ransomware · unauthorised access still live |
**P2** | Is production **still serving but degraded**, or is a compromise **already contained**? | production degraded, slow, or partly broken · one of several nodes down · security compromise already isolated · a workaround exists but is expensive |
**P3** | Is **one service or feature** broken, or is this **non-production**? | a single endpoint or feature erroring · a DTA/dev/UAT environment · a cheap workaround exists · the customer can wait for the normal schedule |
**P4** | No user impact at all? | a false alarm · cosmetic · config drift with no consequence · a finding worth tidying but not urgent |

The axis is **stopped versus degraded**, not how important the server is. It came from
two production-database incidents graded differently:

| Incident | Severity | What its report said |
|---|---|---|
`incident-2026-09-18-ebs-full-acumaticadb` | P1 | *"Operasional transaksi ERP Onemed **terhenti total**"* |
`incident-2026-10-03-pod-prod-db-oom` | P2 | *"production database **impaired**, durasi ± 1h30m"* |

**Three tie-breakers.**

1. **Breadth of impact outranks depth of breakage: if many or all users cannot work,
   raise one level** — however small the broken part is. A single endpoint can stop a
   whole company (SSO, the login path, a shared gateway), and the P3 row's "a single
   endpoint or feature erroring" would otherwise catch it.
   This is not taste, it is the contract. acme-retail's SoW grades severity purely by
   how many people are stopped — *"All users can not work"* = Severity 1, *"Many users
   can not work"* = Severity 2 — and gives Severity 2 a **2-hour** response. Without
   this rule, one broken shared endpoint lands at P3 and its 8 hours: six hours slower
   than what was signed. The scale here stays **P1–P4** and is the only one we grade on;
   this rule is what keeps it from ever being looser than the SoW it is measured against.
   Where our scale is *stricter* than a SoW — non-production is P3 here and Severity 4
   there — nothing needs reconciling: responding sooner than promised breaches nothing.
2. **Security is graded on the compromise, not the environment.**
   `IR-EXAMPLE-UAT-2026-10-05` was ransomware in **UAT** — non-production — and was graded
   **P1**, correctly: the data was already encrypted and the way in was still open. The
   "non-production means P3" line does **not** apply to a security incident.
3. **Unsure between two levels: take the higher one**, then lower it if it turns out
   wrong. Raising a severity can be corrected; an incident handled too casually cannot be
   replayed. And since the weight follows the severity, correcting it is one banner line.

Checked against the ten named incidents above and in the open-items list: none
contradict these criteria. They describe the calls already made rather than changing
them.

### Multiplier and adder

- **×1.5 if production.** Non-prod (DTA/preprod) ×1.
- **+3 for cross-layer investigation OR rework outside normal procedure.**
  Cross-layer example: FFI-TerminalSrv on 29 Sep (OS → RDS licensing → AD).
  Rework example: #319 qms — three failed SSM Automation retries that left 8 orphan
  volumes behind.

Round to whole numbers. Decimals imply precision that is not there.

### Weighting principles

1. **One issue = one weight.** Never sum per action item. Action items are execution
   detail; weight sits at deliverable level. (This is also why "one sub-issue per
   action item" was rejected — fragmentation without benefit.)
2. **Fan-out via one sub-issue per server, not a multiplier.** Batch #79 → #316,
   #330–#335: each child carries its own weight, so the total accumulates naturally.
3. **Cross-issue work is counted ONCE, at the umbrella.** The 28 Sep volume cleanup
   touched 11 issues; if each claimed it, effort done once would be counted 11 times.
   Weight it once at the umbrella (#27), mark Done in the children without a separate
   weight, and **say so on the weight line** so nobody counts it again later.
4. **Other parties' work is not Example MSP weight.** App verification by Tim App is zero Example MSP
   weight even though it consumes calendar time.

### Examples (acme-retail, actual values as of 2026-09-29)

| Issue | Calculation | Weight |
|---|---|---|
| #316 vmi-prd upgrade (clean run) | change-high 8 × prod 1,5 | **12** |
| #319 qms-prd upgrade (3× SSM retry + orphan volumes) | 8 × 1,5 + 3 rework | **15** |
| #315 microstrategy-prd upgrade (domain secure channel broken post-cutover) | 8 × 1,5 + 3 cross-layer | **15** |
| #109 benderapay AL2→AL2023 (OS → nginx/TLS → ALB/TG → DNS in another account → app config) | 8 × 1,5 + 3 cross-layer | **15** |
| #330/#331 uipath-studio-**dta** | 8 × non-prod 1 | **8** |
| #332–#335 uipath-robot / RPA (**prd**) | 8 × 1,5 | **12** |
| #345 benderapay DTA environment (clone EC2 + RDS PITR + new ALB/TG) | change-high 8 × non-prod 1 | **8** |
| #27 EBS-003 cleanup sweep (27 volumes, 11 issues) | change-low 3 × 1,5 + 3 analysis | **8** |
| #79 upgrade batch umbrella | not weighted — children carry it | **—** |
| Monthly report | check | **1** |

Umbrella issues are **not** weighted on their own (#79); their children are. The one
exception is an umbrella that hosts a cross-issue sweep (#27), and there the weight line
must say it covers only that sweep.

### Where the weight is recorded

**Canonical — a line in the issue body** (and, once the ticket template is aligned, in
the ticket file). Works for all customers with no setup:

```
> **Bobot kerja:** 12 — `change-high` (8) × produksi (1,5)
```

The format must be exact so it can be parsed. The number goes immediately after
`**Bobot kerja:**`; the reasoning follows after the `—`.

**The mirror is not optional once a chart reads it.** GitHub Projects Insights charts
from the BOARD, so a weight living only in markdown is invisible there. Measured on
acme-retail 2026-10-05: 11 issues carrying a weight in the body had none on the board,
worth 98 — a capacity chart would have reported 230 against a real 328, wrong by 30%
with nothing indicating it. `sync_weight_to_board` closes that mechanically, and `ticket_file_sync_to_issue` now
sets it on create so the catch-up is a one-off rather than a standing chore — without
that, the gap regrows after every cleanup, because nothing in the create path touched
the board at all. The two
sources had zero conflicting values and nothing board-only, so markdown was a strict
superset and the gap was purely un-mirrored.

**The mirror — a `Weight` NUMBER field on the project board.** Since 2026-10-13 every customer
has a board: its own (`github_project:` in customer.yaml) or the shared org board #60 with a
`Customer` column; the tools pick the right one. Before that, only 4 of 46
customers have a Managed Service board (acme-retail #46, acme-retail #44, example-d #35,
example-e #47), so the board cannot be the primary mechanism. Where a board
exists the field is a convenience for sorting and summing in the UI. **If the two
disagree, the markdown wins.**

acme-retail board field ID: `PVTF_lADOBCxoZc4Bd-o1zhjyWu4`

Keeping the canonical value in markdown also means the weight is committed to git, so
it is auditable — when it was set, and whether it was ever changed. A board field has
no history.

### Aggregating

`report_work_weight(customer, period)` does it. It reads `Bobot kerja` from the issue
bodies, groups by assignee and by the board's `Segment`, and filters a period on
**closedAt** — capacity is about when work landed, so an issue still open has not landed.

It reports the gaps instead of printing a clean number, because a capacity figure that
is wrong without saying so is worse than none:

- an unfilled `<n>` placeholder is **excluded from the total and listed**; a placeholder
  parses as nothing, so it silently shrinks the number — 88 migrated tickets sat in that
  state and the gap was invisible until someone went looking;
- issues with **no assignee** are counted in the total but listed separately: per-person
  capacity drawn from rows that name nobody is not capacity planning;
- **co-assignees split** one issue's weight rather than each claiming it, so two names
  cannot inflate the total past what was done;
- two logins are merged only when `ALIASES` says so. `zakinurw` / `zakinw` looked like
  one person across two accounts; guessing would quietly halve somebody's load.

An umbrella needs no special case for the total: it has no weight line, so it
contributes nothing. But it IS separated in the gap report, because "umbrella, correctly
unweighted" and "leaf, weight forgotten" are opposite instructions. They used to share
one bucket, so the worklist handed to an engineer mixed *fill this in* with *leave this
alone* — 11 of the 48 acme-retail issues flagged as missing a weight were umbrellas.
Detected from the native sub-issue relation (`subIssues.totalCount`), one paginated
GraphQL call per customer. A weighted umbrella such as #27 never reaches the split: it
has a weight line and counts normally.

First run on acme-retail (2026-10-02, open issues): 14 weighted, total 160 — Change 64,
no Segment 61, Project 27, BAU 8. And the honest part: **95 of that 160 has no
assignee**, and 53 issues carry no weight line at all.

**Segment comes from the board, not a label.** A first version read a `segment:` label
and every issue came back empty — the only label in this repo is `customer:<slug>`.

### Quality counterweights — kept separate from weight

Do not fold these into the weight number:

- **Recurrence** — an incident that returns within 30 days is a negative signal about
  the *process*. #343 recurred on 29 Sep precisely because its three preventive
  follow-ups from 24 Sep (session timeout, RAM upsize, memory alarm) were never closed.
- **Share of preventive action items closed** — not just the incident itself.

Without these, the only thing measured is how fast tickets are closed.

### Usage warnings

- **For capacity planning, not individual ranking.** Who gets the heavy tickets is not
  the engineer's choice; without accounting for assignment distribution, what is being
  measured is the assignment decision.
- **If the KPI unit is split finer, people will split finer.** That is a rational
  response to a measure, not cynicism.
- **If comments are scored, comment honesty drops** — people stop writing "my
  hypothesis was wrong", which is the most valuable kind of comment.
- **Recalibrate after ~1 quarter.** The numbers above are initial estimates. If every
  `change-high` feels like 5 rather than 8, lower it. An uncalibrated weight table gets
  abandoned.

---

## Tooling contract

The shape is produced and maintained by `msops/` — as of 2026-09-29 this is
automatic, not manual. Four places read a ticket file, and **all four must be kept
in step**; changing the template alone breaks the others silently for every
customer:

| Code | Reads / writes | Contract it depends on |
|---|---|---|
| `artifacts.create_ticket` | writes the shape | the 5 blocks + `## Riwayat` (ticket file only — the issue body has no `## Riwayat`). No `## Referensi`; documents go in the `Dokumen` row of `## Environment` |
| `workflow.update_ticket_status` → `related_doc` | fills the `Dokumen` row | `\| Dokumen \| … \|` in `## Environment`; several documents accumulate on that one row. Legacy tickets still use the 2-column table |
| `workflow.update_ticket_status` | rewrites the banner, appends history | `> **Status:** …` and `> **Update terakhir:** …` on the banner; a `## Riwayat` (or legacy `## Status History`) table |
| `integrations._extract_ticket_fields` | reads Status → drives issue open/close | Status must be parseable from the banner line, cut at the first `·`. It also feeds `sync_ticket_to_zoho`, but that path has no evidence of use — do not treat it as live |
| `integrations.sync_ticket_to_github` | creates/updates the issue, links the umbrella | returns the issue `number` on every path; an optional `**Parent**: #N` line becomes a native sub-issue link (the API needs the child's database id, not its number) |
| `tracker.list_open_action_items` | lists open action items | action-items table rows; any Status cell that is not Done counts as open. **Reads local files only** — action items in the 70 issues without a ticket file are invisible to it |
| `issue_audit.audit_issue_format` | audits issue bodies, writes nothing | the 5 blocks, the banner, the five PM questions |
| `issue_audit.pending_in_comments` | flags open `- [ ]` items that exist only in a comment | the action-items table; content inside `<details>` is history and ignored |
| `issue_cleanup.split_detail_to_comment` | moves a detail block to its own comment, returns the url to link | nothing — it never touches the body |
| `integrations._wire_board` | on CREATE only, sets the board Weight / Status / Segment a new issue can be born with | `Bobot kerja` in the derived body; ticket Status mapped to a board column (six states, four columns); task type mapped to Segment. Never fails the issue creation — the board is a mirror, and losing a field must not lose the issue |
| `board.set_board_fields` | writes Status / Segment / Weight / Due on one issue | board number from `customer.yaml`; a single-select value must match a declared option — `gh` accepts a wrong option id and the write lands empty |
| `weight_sync.sync_weight_to_board` | mirrors `Bobot kerja` onto the board Weight field | markdown -> board only; skips issues with no numeric weight (umbrellas included); reports an issue absent from the board rather than adding it |
| `scope.sow_status` | says whether a customer is gated on SoW classification, and why not if it is not | `sow:` in `customer.yaml`, with a trailing `# comment` stripped; a `sow:` naming a missing file is reported, not treated as ungated |
| `scope.scope_candidates` | SoW clauses worth READING for an activity — never a verdict | both sides always returned; sections classified by heading (before the first `##` = in scope, `## Out of scope` = out, the rest = reference); `weak_match` when the best overlap is ≤ 1 |
| `scope.report_out_of_sow` | lists the activities recorded as outside the SoW | the `> **Scope:**` banner line; `closedAt` for the period. Carries no weight — that scale does not leave the building |
| `weight_report.report_work_weight` | totals weight per assignee and per Segment | `**Bobot kerja:** <n>` in the body; `Segment` from the board; `closedAt` for the period |
| `issue_write.update_action_item` | flips one row, refreshes the banner, posts the dated comment, links it back into the row | row numbering in `## Action items`; the 4 status emoji; `> **Update terakhir:**` |

Two traps worth remembering, both found while implementing this:

- **`update_ticket_status` must refresh the banner, not just append history.** The
  previous implementation only appended a history row and never touched the header,
  which is *the* mechanism by which bodies went stale — a closed ticket could still
  read `Status: Open` (#316).
- **Do not name task types in the scaffold.** `integrations._extract_task_type`
  infers the Zoho task type by keyword-scanning the whole ticket, so spelling out
  "change-high" in a weight hint would mislabel every new ticket. The weight table
  is referenced by path instead of inlined, for exactly this reason.

Legacy tickets (the `**Status**: Open` + `## Status History` shape) are still
read and updated correctly — every parser accepts both shapes, and
`tests/test_ticket_format.py` locks that down.

### Sync does not own the issue body

**Decided 2026-09-30, reversing the earlier answer.** `ticket_file_sync_to_issue` used to
push the ticket **verbatim** and overwrite the body on every run, which was called
harmless "because ticket and issue share one shape". They must not share one shape:

- the **ticket file** is the working document and needs `## Riwayat`, because
  `update_ticket_status` appends there and that is what keeps its banner fresh;
- the **issue body** must not have `## Riwayat`, because it duplicates the banner.

#316 proved it. Its ticket file and issue body were byte-identical, so tidying the body
and then re-syncing the ticket would put `## Riwayat` straight back — silently undoing
the work. §6.1 of the rollout plan counts **56 issues already drifted** from their
tickets, so re-syncing is not hypothetical.

Therefore sync writes the body **only when it creates the issue**, and what it writes is
derived from the ticket — banner, Environment, Masalah, Action items — without
`## Riwayat` and without the investigation prose. On an existing issue it syncs labels
and the parent relation, and **leaves the body alone**. The issue body is canonical;
`issue_update_action_item` and `issue_rewrite_body` maintain it.

**State follows the same rule (2026-10-01).** The ticket Status sets open/closed only at
creation. On update a disagreement is reported as `state_mismatch` and nothing is
changed. The old behaviour reopened a closed issue whenever its ticket still read
"In Progress" — measured across ms-ops that applied to **12 correctly closed issues**,
among them #239/#240/#241/#242, Windows upgrades that were finished and whose ticket
files were simply never updated. (#133 was in the list for a second reason: the
`**Status:**` regex leaks `**` into the parsed value, so `** Resolved` fails the
first-word match.) A mismatch is reported rather than discarded because it means the
ticket file needs attention. Closing is now `issue_update_action_item`'s proposal once every
item is Done, with a human approving.

This also protects the six issues whose hand-written bodies are better than their ticket
files (#261, #262, #271, #275, #277, #278, found in §6.2).

One trap when migrating a ticket by hand: `ticket_file_sync_to_issue` decides
open-versus-closed from the **first word** of the banner Status, matched against
`resolved` / `closed` / `done`. A banner reading `Status: Selesai (closed)` parses as
"selesai" and would **reopen** a closed issue. Use the vocabulary the tool knows:
Open · In Progress · Pending Approval · Resolved · Escalated · Closed.

---

## Reference

- Full worked example: [#316](https://github.com/your-org/ms-ops/issues/316) — body
  99 → 46 lines, old body preserved in an
  [archive comment](https://github.com/your-org/ms-ops/issues/316#issuecomment-5888688703)
- Problem being avoided: [#343](https://github.com/your-org/ms-ops/issues/343) — one
  issue holding two incidents with different root causes
- Rollout record and rationale: `docs/plans/2026-09-29-issue-format-and-work-weight.md`
