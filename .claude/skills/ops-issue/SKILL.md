---
name: ops-issue
description: >-
  Issue-first workflow for customer operations on GitHub Issues, in four
  stages: Get (file or pick up the issue, make sure it has an owner), Analyze
  (read, verify, derive action items), Ship (execute with approval, keep the
  issue body current), Done (reply, resolve, close). Use when the prompt asks
  to file, create, triage, assign, work on, continue, update or close an issue
  ("buat issue", "assign issue", "kerjakan #123", "lanjut #123"), asks which
  issues have no owner or have gone stale, or reports progress on an action item.
metadata:
  version: "1.2.0"
---

# Issue-first operations

The GitHub Issue is the source of truth for the work. Its **body is the state
now**; **comments are the dated evidence trail**. Full format:
`docs/standards/ops-issue-format.md` (summary in
[references/issue-body.md](references/issue-body.md)).

```
Get  -->  Analyze  -->  Ship  -->  Done
Todo      In Progress   In Progress / Pending Approval   Done
```

Who runs which stage is the team's business, not this skill's. **Do not work out
the stage yourself: call `issue_next(N)` first.** It returns the stage and the one next
step with its command, the same answer the banner's `Tahap` and `Next` lines carry. For
a daily queue use `issue_list(stage="Get")` and `issue_list(stage="Analyze")`; rows
marked `stuck` have sat there more than 3 days.

## Rules for every stage

1. **One issue = one story.** A change that comes out of an issue is a **new
   issue** that mentions the old one (`Related: #N`). No sub-issues, no
   `**Parent**:` line. A new incident on an old problem is a new issue:
   `Recurrence of #N`.
2. **Progress goes through `issue_update_action_item`, never a free-form comment.** It
   updates the table row, recomputes the banner (`Next`, `Bola di`) and posts
   the dated evidence comment in one call. Do not post a progress report,
   checklist or status heading ("Progress Update", "DONE", "Sisa") by hand: it
   leaves the body stale and hides the open items in a comment.
3. **Long detail** (inventories, command output, AMI lists, step lists) goes to
   a comment with `issue_move_detail_to_comment`; the action item row links to it.
   Do not repeat it in the body.
4. **Targeted updates.** Routine progress uses the action tool, not a full rewrite or
   body archive. Preserve unique facts before removing them; reserve `issue_rewrite_body`
   for structural/substantive replacement. Comment format lives in the writing standard.
5. **Approval once per bounded plan.** Follow `ops-rules.md` rules 4–5 (normal and
   YOLO/end-to-end). Defaults stay `dry_run=True`; already-approved routine evidence,
   docs and closure updates can execute directly. Preview substantive rewrites.
6. **Do not use `ticket_file_sync_to_issue` for issue-first work.** It builds an
   issue from a finished ticket file and refuses one whose action items are still
   a placeholder or whose `Bobot kerja` is unfilled. Issue-first work starts on
   GitHub with `issue_create`.
7. No emoji in titles, bodies or comments. Artifacts are English; chat follows
   the user's language.
8. Changing a customer's resources needs explicit approval, as in the `ms-ops`
   hard rules. Editing the issue is not approval to change infrastructure.

## Stage 1: Get

Goal: an issue exists, has an owner, and sits at `Todo`.

**No issue yet**
1. `get_customer(<name|account|ip>)`. Ambiguous: ask one question. **No match: ask
   before anything else** whether this is a new contracted customer (then
   `create_customer`) or a one-off request from a party without a managed-service
   contract (pay per request, "token"). A one-off goes under customer `token`: pass
   `engagement=<client name>` to `issue_create`. Do not guess between the two. `token`
   has no SoW and no
   monthly report; the weight and the approval rules are the same.
2. `check_recurrence(customer, <keywords>)` and `issue_find(<keywords>)`.
   If an open issue already covers it, point to it instead of filing a
   duplicate.
3. Collect what is missing, one question at a time: **symptom**, **impact**,
   **evidence**, **requester**, **environment** (prod or non-prod, resource if
   known).
4. `issue_create(customer, title, symptom, impact, requester, environment,
   resource, evidence, dry_run=True)`. Pass `actions` only when the request is
   already concrete ("restart server X"); otherwise one placeholder row is
   written and Analyze replaces it. Show the preview (title and body, see
   [references/issue-body.md](references/issue-body.md) "Get body") and wait for
   approval.
5. Run it again with `dry_run=False`. It refuses an unknown customer, a missing
   field, emoji and a duplicate title, labels `customer:<slug>`, and sets the
   board status to `Todo`. Without the tool: `gh issue create --repo
   your-org/ms-ops --label customer:<slug> --title ... --body-file ...`.

**Issue has no owner**
1. `issue_list(assignee="none")` (add `customer=` to narrow): unowned open
   issues, most idle first. Add each person's current load with
   `report_work_weight(customer)`. For a stale sweep use `issue_list(idle_days=30)`.
   Without the tool: `gh issue list --repo your-org/ms-ops --state open
   --search "no:assignee" --json number,title,labels,createdAt`.
2. Suggest an assignee (lightest load, then who knows the customer). It is a
   suggestion; the user decides.
3. After the user names the assignee: pass it as `login` to `issue_analyze` in Stage 2,
   which sets the owner in the same approval. `issue_assign(N, login)` alone is for an
   issue that is already analysed. An issue may not be marked `done` or resolved without
   an owner (the tools refuse).

## Stage 2: Analyze

Goal: the body tells a PM where things stand, and every action item is verified
before it is done.

1. **Read once.** `issue_get(N)` returns the body and recent bounded comments;
   `include_history=True` is for a specific history question. Reuse current context,
   refreshing after writes or concurrent changes as needed. `get_customer`, `doc_index(customer, query=<topic>)`,
   `search_customer_kb`, `check_recurrence`. Docs first; verify live only what
   the docs do not answer. If `doc_audit_freshness(customer)` flags the doc you rely on as
   `stale` or `behind`, treat it as a hint, not a fact, and verify before using it.
2. **Check the body.** It must answer the five PM questions without opening
   comments (where it stands, whose ball, next step, last movement, blocker).
   If not, rewrite it with `issue_rewrite_body` (dry run, old body archived).
   `issue_audit_format(customer, N)` shows what is wrong.
3. **Action items and classification, one call.** `issue_analyze(number, type, env,
   actions=["Action | PIC", ...], priority, scope, scope_reason, kind, login,
   dry_run=True)` replaces the placeholder row with the real rows (one action, a PIC,
   status `Pending`), sets the owner when `login` is given, writes weight and scope as
   below, turns the banner to Tahap Ship and mirrors the board; one preview, one approval.
   It refuses a table that already holds real rows; there, and to reclassify, use
   `issue_classify(number, type, env, priority, scope, scope_reason, dry_run=True)`:
   it computes `Bobot kerja` from the standard table (never type the number), writes
   the `Scope` line and label only for a customer whose `customer.yaml` names a `sow:`
   (`sow_status`; read `scope_candidates(customer, <activity>)` first, the user decides,
   never keyword matching; customers without `sow:` get no Scope line at all), mirrors
   weight and segment to the board, and posts one dated comment with the decision.
   `env` and `priority` are your judgement; ask if unclear. `issue_audit_format` flags
   an issue while the weight is still `TBD`. Sustained multi-deliverable work is a
   **project** (`kind="project"`): this issue becomes the umbrella, `doc_create_project`
   scaffolds `projects/<name>/` (brief, timeline with mandays, TDD, tracker, handover),
   one issue per phase carries `**Parent**: #umbrella`, and each phase gets a full MoP
   via `doc_create_project_mop`. The TDD is approved before any execution phase.
4. **Verify each item, read-only.** Is the problem still present, is the
   resource what the row says. Record it with
   `issue_update_action_item(..., status="in_progress", note=<finding>)`; it is refused
   while `Bobot kerja` is still `TBD` (run step 3 first; `force=True` only with the reason
   in `note`, and it is recorded). If it
   differs from the earlier suspicion, write "previously suspected X, corrected
   to Y" in the body. **When what you read live differs from the customer docs, say so
   in the finding: that is a Docs Delta, handled in Stage 3 and 4.**

## Stage 3: Ship

Goal: each action item executed, with evidence in the body trail.

1. Execute the approved plan (normal or end-to-end mode), then
   `issue_update_action_item(..., status="done", note=<evidence>)` (needs an owner).
   Blocked by access or another team: `status="blocked"` (banner `Escalated`) and name
   whose ball it is. Waiting for an approver: `status="pending_approval"`. Work Example MSP
   finished that now waits for an approval is two rows: the work `done`, and a separate
   approval row (PIC = who decides) set to `pending_approval`.
2. **Document only if an item needs it.** A MoP or incident report is created
   with `doc_create_mop` / `doc_create_incident_report` (`dry_run=True` first), then
   filled in with `ops-report`. Link it from the `Dokumen` row in Environment.
3. **Docs Delta, at the moment you have the data.** After an action item that created,
   changed or removed a resource is `done`, or when a live read contradicted a doc, draft
   the update to the affected core doc (`<slug>/docs/instances.md`, `network.md`, ...) as a
   small diff; apply under the plan's approval (or obtain approval if not covered) and set the doc's
   `Terakhir diverifikasi` line (see `docs/standards/ops-docs-schema.md`). Commit with
   `Refs #N`. Do not leave it for the close-out: by then the data is cold.
4. **A change comes out of it.** Create a new issue (Stage 1, `Related: #N`) and
   mention it in the Notes block. No sub-issue.
5. **Status at every step.** The banner is derived from the rows: `In Progress` while
   anything is open or when every row is done but Done (below) has not happened,
   `Pending Approval` while waiting for an approver, `Escalated` while blocked by
   someone else. The board card (Status, Weight, Segment) follows by itself whenever a
   tool writes the issue: the customer's own board when it has `github_project:`,
   otherwise the shared org board #60 (Customer column set for you). The banner is the
   source; the board is the mirror. `issue_set_board_fields` is only for a value the
   issue cannot state, such as `Due`.

## Stage 4: Done

1. Fix executed and verified; actual completion communication recorded, or explicit
   operator-directed closure recorded per `ops-rules.md` (identify any communication
   follow-up truthfully):
   `issue_resolve(N, reply_evidence=<when and how the reply went>,
   docs_delta="diperbarui: <files>" | "tidak ada perubahan", source=<who decided,
   e.g. "atas instruksi <user>; persetujuan <name> via <channel> <date>">, dry_run=True)`,
   then `dry_run=False` after approval; an end-to-end plan that explicitly includes
   closure already supplies it for this routine write. It writes the `Docs Delta` row, sets the banner to `Resolved`,
   posts the RESOLUTION comment, closes the issue and sets the board to Done. Every row
   `done` does NOT do this by itself; closing is a person's decision. It refuses while
   rows are open (`force=True` records why) or the issue has no owner.
2. Commits and PRs use `Refs #N`, never `Closes #N`.
3. Verify closed state and board once; summarise outcome and evidence links briefly.
   At each checkpoint use Performed / Verification / Result in the note; the tool
   supplies the action reference and links it from the table. If the fix was not obvious, propose a KB entry
   (`doc_create_kb_entry`, apply only after approval).
