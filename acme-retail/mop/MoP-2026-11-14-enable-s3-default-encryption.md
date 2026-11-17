---
type: mop
summary: "Enable default encryption and TLS-only policy on the uploads bucket"
tags: [s3, encryption, wafr, remediation]
applies_to: [acme-prod-uploads]
parent: "#1"
---
# MoP: Enable S3 default encryption

**Document Title:** MoP - Acme Retail Enable S3 default encryption
**Document Name:** MoP-2026-11-14-enable-s3-default-encryption
**Status:** executed

## Document Management

| Role | Name | Date |
|------|------|------|
| Creator | Kiro CLI | 2026-11-14 |
| Quality Control | Cloud engineer | 2026-11-14 |

## Sign Off

- Created by: Kiro CLI
- Checked by: Cloud engineer
- Approved by (Customer): Acme Retail operations lead

## Requested Information

- **Description:** Enable SSE-S3 default encryption and require TLS on `acme-prod-uploads`
- **Customer AWS Account ID:** 123456789012
- **AWS Service:** Amazon S3
- **Environment:** Production

## Current State

Verified 2026-11-14: `get-bucket-encryption` returns no configuration.

## Risk Assessment

- **Risk Level:** Low
- **Impact:** None for readers and writers. New objects are encrypted, existing objects are unchanged.
- **Blast Radius:** One bucket

## General Work / Activity

| No | Step | Command | Expected Output |
|----|------|---------|-----------------|
| 1 | Check current state | `aws s3api get-bucket-encryption --bucket acme-prod-uploads --profile acme-retail` | Error: not found |
| 2 | Enable default encryption | `aws s3api put-bucket-encryption --bucket acme-prod-uploads --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' --profile acme-retail` | No output |
| 3 | Verify | `aws s3api get-bucket-encryption --bucket acme-prod-uploads --profile acme-retail` | `AES256` |
| 4 | Add TLS-only deny policy | `aws s3api put-bucket-policy --bucket acme-prod-uploads --policy file://tls-only.json --profile acme-retail` | No output |

## Rollback

`aws s3api delete-bucket-encryption --bucket acme-prod-uploads --profile acme-retail`
and `aws s3api delete-bucket-policy --bucket acme-prod-uploads --profile acme-retail`.

## Verification

- Step 3 returns `AES256`.
- A test upload over HTTP is denied, over HTTPS succeeds.
