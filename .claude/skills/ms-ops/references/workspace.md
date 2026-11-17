# Customer workspace

Where things live in a customer folder and which file name each artifact
gets. The full contract is `ops-rules.md` → "Customer Workspace Contract";
`python3 scripts/audit_customer_completeness.py` checks it.

## Slug

Folder name = `customer.yaml` `folder:` = registry slug. Lowercase
kebab-case, no dots, no capitals. Never invent a variant.

## Core docs (required for managed customers)

| File | Holds |
|---|---|
| `<slug>/customer.yaml` | Manifest: profiles, accounts, providers, `managed`, read-only flags |
| `<slug>/docs/overview.md` | Account IDs, profile, region, VPC CIDR, business context |
| `<slug>/docs/instances.md` | Compute inventory: ID, type, IP, SG, volumes, workload |
| `<slug>/docs/network.md` | VPC, subnets, SG rules, EIP, routing, load balancers |
| `<slug>/docs/access.md` | Key pairs, IAM roles, SSM, bastion, VPN, domains |

Read with `read_customer_doc(customer, "<doc>")`. `managed: false` opts a
one-off customer out of the contract.

**Multi-account customers** (acme-retail, acme-retail) keep per-account facts in
`<slug>/docs/<account>/`; read with `read_customer_doc(customer,
"<account>/<doc>")`. Artifacts stay at customer level and name the account
inside. `<slug>/accounts/<name>/` is an older layout (example-a, example-b, example-c):
read it, never create new ones. `<slug>/infra/<name>/` holds IaC, usually a
submodule.

## Artifacts (created on demand)

Create them through the MCP scaffold tools, not by hand. Each tool renders a
template from `template/` (see the `ops-report` skill for the full
artifact → template map); to change a format, edit the template.

| Artifact | Path | Tool |
|---|---|---|
| Ticket file (legacy; new work starts as a GitHub Issue) | `<slug>/tickets/YYYY-MM-DD-<slug>.md` | none for new files (`ticket_file_update_status` edits existing ones) |
| MoP (approval + procedure, one per change) | `<slug>/mop/MoP-YYYY-MM-DD-<slug>.md` | `doc_create_mop` |
| Incident report | `<slug>/incident_report/incident-YYYY-MM-DD-<slug>.md` | `doc_create_incident_report` |
| MoM | `<slug>/mom/MoM-YYYY-MM-DD-<slug>.docx` | `doc_create_mom` |
| KB entry | `<slug>/knowledge-base/KB-YYYY-MM-DD-<slug>.md` | `doc_create_kb_entry` |
| Assessment | `<slug>/assessment/ASMT-YYYY-MM-DD-<slug>.md` | `doc_create_assessment` |
| Project work | `<slug>/projects/<name>/` | — |
| Monthly report | `monthly-report/output/<slug>/<YYYY-MM>/` (markdown only) | `doc_create_monthly_report` |

`assessment/` holds one standalone analysis with a conclusion. A multi-phase
engagement with its own deliverables goes in `projects/<name>/`. A finding
worth reusing goes in `knowledge-base/`.

## Knowledge base

Propose a KB entry when the session produced reusable knowledge:
troubleshooting that took more than two steps, a config choice with its
rationale, an IAM change, a recurring request, a workaround, an architecture
decision. Skip trivial checks and anything already in the core docs.
Customer-specific → `<slug>/knowledge-base/`; generic → `kb/`.

## Credentials

Never commit credentials, not even as defaults in scripts or forms.
