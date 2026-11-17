# Access - Acme Retail

- **Method:** AWS IAM Identity Center (SSO), role `aws_ms`
- **Login:** `aws sso login --sso-session example-sso`
- **Admin host access:** SSM Session Manager to `acme-bastion`, no inbound SSH
- **Break glass:** documented in the customer's own runbook, not stored here
