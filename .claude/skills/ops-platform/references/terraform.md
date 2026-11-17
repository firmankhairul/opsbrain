# Terraform playbooks

Scope: Terraform / OpenTofu / terragrunt state, drift, import, and plan/apply hygiene for customer IaC.

## Plan / apply flow
1. `terraform init` against the remote backend; confirm workspace (`terraform workspace show`) matches the target environment.
2. `terraform plan -out=<planfile>` — share the output in the Change Proposal. Any `destroy` or `-/+ replace` makes the change L3.
3. Back up state (`terraform state pull > <backup>.tfstate`) before apply or any state command.
4. `terraform apply <planfile>` only after approval; never apply an unsaved plan.
5. Verify with a follow-up `terraform plan` that reports no changes.

## State management
1. `terraform state list` — inventory managed resources.
2. `terraform state show <resource>` — inspect attributes.
3. `terraform import <resource> <id>` (L2) — bring existing infra under management. Always `plan` first.
4. `terraform state mv <src> <dst>` (L2) — refactor without destroy. Back up state first.
5. `terraform state rm <resource>` (L3) — resource becomes unmanaged.
6. Backend migration: `terraform init -migrate-state` (L3) — requires a state backup.

## Drift detection
1. `terraform plan` — identify unexpected changes.
2. Out-of-band change → decide: import and reconcile (preferred) or targeted destroy+recreate.
3. Prevention: tag policy, SCPs, AWS Config rules.

## Best practices
- Pin provider versions `~> X.Y`.
- Remote state only (S3 + DynamoDB lock / GCS / Azure Blob).
- Never store secrets in state; use Secrets Manager (or equivalent) references.
- `terraform plan` output is a PR artifact. Save planfiles.
- Prefer `moved` blocks over state manipulation (Terraform >= 1.1).
