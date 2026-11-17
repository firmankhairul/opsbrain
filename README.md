# OpsBrain: One Shared Skillset for Cloud Support Teams

OpsBrain is a Kiro workspace for managed-services providers (MSPs). One GitHub
repository gives every cloud engineer the same skills, customer knowledge, MCP
tools and approval rules, so work is done the same way no matter who is on shift
or which customer is being supported.

Built for Kiroween 2026 with Kiro CLI, MCP and GitHub.

> All customer data in this repository is fictional. `acme-retail` is an example
> customer. Account IDs, names and addresses are placeholders.

## The problem

An MSP serves many customers with many engineers. Each engineer has their own
prompts, scripts and habits. New people take weeks to learn each customer.
Knowledge lives in chats and personal notes, so the same incident is fixed
differently depending on who is on shift.

## What it does

- **Unified skills:** eight ops skills with one entry point (`ms-ops`) that resolves
  the customer, reads its docs first, classifies the task and routes it.
- **Full lifecycle driven by Kiro:** first assessment, Well-Architected Framework
  Review (WAFR), remediation issues, MoP creation, approved execution and a
  knowledge base.
- **ITSM on GitHub:** incidents, changes and findings are GitHub Issues with a
  standard format, an action-item table and a work weight. Repair steps and status
  are centralized there and kept up to date by Kiro.
- **Kiro CLI analysis and remediation:** Kiro reads the alert, checks the live
  state read-only, proposes a fix, waits for approval, executes and records the result.
- **Approval gates:** no mutating action runs without explicit approval.
  The rule is propose, wait, then execute.

## Integrations

| Integration | How |
|-------------|-----|
| GitHub (issues, PRs, repos) | MCP server `github` |
| AWS documentation, pricing, Well-Architected security | MCP servers `aws-documentation`, `aws-pricing`, `aws-well-architected-security` |
| Truewatch observability | MCP server `truewatch` |
| Customers, docs, tickets, reports, SoW scope | MCP server `ms-ops` (`msops/server.py`) |
| Zoho Desk | Python tools in `msops/tools/integrations.py` |
| Gmail | Python tools in `msops/tools/gmail.py` |
| GCP, Huawei Cloud, Datadog, other clouds | Skill guides in `.claude/skills/ops-cloud/references/`. Their MCP servers are optional and disabled by default. |

## Repository layout

```
.claude/skills/        8 ops skills (source of truth)
msops/                 MCP server and tools (Python)
scripts/               setup and sync scripts
docs/standards/        issue format, docs schema, output contract
template/artifacts/    assessment, MoP, MoM, incident report, KB templates
acme-retail/           fictional example customer (full lifecycle)
ops-rules.md           workflow and approval rules
```

## Example: the full lifecycle for `acme-retail`

1. `acme-retail/assessment/ASMT-2026-11-03-first-assessment.md` - baseline assessment
2. `acme-retail/assessment/ASMT-2026-11-10-wafr-review.md` - WAFR with ratings and findings
3. `acme-retail/tickets/2026-11-11-remediate-wafr-findings.md` - issue with action items
4. `acme-retail/mop/MoP-2026-11-14-enable-s3-default-encryption.md` - approved MoP
5. `acme-retail/knowledge-base/KB-2026-11-15-s3-default-encryption.md` - reusable fix

## Quick start

```bash
git clone https://github.com/<your-user>/opsbrain.git
cd opsbrain
cp .env.example .env        # fill in only the integrations you use
bash scripts/setup.sh       # skills, MCP config, hooks
```

Open the folder in Kiro (or Kiro CLI) and try:

```
Review acme-retail and tell me which WAFR findings are still open.
```

## Safety

- Read-only first. Mutating actions need explicit approval.
- Secrets live in `.env` or a vault, never in the repo.
- No emoji in reports, issues or tickets. Status is plain words.

## License

MIT. See `LICENSE`.
