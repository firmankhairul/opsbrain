# S3 default encryption remediation

**Date:** 2026-11-15
**Tags:** s3, encryption, wafr, remediation, troubleshooting

## Symptom

WAFR or Security Hub reports a bucket without default encryption.

## Fix

1. Confirm with `aws s3api get-bucket-encryption --bucket <name>`.
2. Enable SSE-S3 with `put-bucket-encryption`. Use SSE-KMS only if the customer needs key control.
3. Add a bucket policy that denies requests where `aws:SecureTransport` is false.
4. Verify with `get-bucket-encryption` and a test upload.

## Notes

- Existing objects stay unencrypted. Re-copy them in place if required.
- Low risk, normally change-low with a short MoP.
