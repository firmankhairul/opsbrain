# Assessment: First assessment (onboarding baseline)

**ID:** ASMT-2026-11-03-first-assessment
**Customer:** Acme Retail
**Date:** 2026-11-03
**Author:** Kiro CLI, reviewed by a cloud engineer
**Status:** final

## Verdict

The environment is healthy and ready for managed services. It has four gaps
worth fixing early: no AWS Config, a single NAT gateway, an unencrypted uploads
bucket and a database parameter group with the default log retention.

## Scope

**In scope:** account 123456789012, region ap-southeast-1, networking, compute,
database, storage, access and security services (read-only).

**Excluded:** application code, third-party SaaS, other AWS accounts.

## Current State

**Verified:** 2026-11-03 via AWS CLI read-only calls (`describe-*`, `list-*`).

| Item | Observed | Source |
|------|----------|--------|
| VPC | 10.20.0.0/16, 3 subnet tiers across 2 AZs | `ec2 describe-subnets` |
| Compute | ECS Fargate service `acme-api`, 3 tasks | `ecs describe-services` |
| Database | RDS PostgreSQL 15, Multi-AZ, backup 7 days | `rds describe-db-instances` |
| Storage | 2 S3 buckets, uploads bucket without default encryption | `s3api get-bucket-encryption` |
| Access | SSO role `aws_ms`, SSM only, no SSH | `ssm describe-instance-information` |
| Security | GuardDuty, Security Hub, CloudTrail on; Config off | `securityhub describe-hub` |

## Recommendation

Run a Well-Architected review next (see ASMT-2026-11-10-wafr-review), then
remediate through GitHub Issues with an approved MoP for each change.

## Findings

### 1. Uploads bucket has no default encryption

**Evidence:** `get-bucket-encryption` returns `ServerSideEncryptionConfigurationNotFoundError`.
**Impact:** customer uploads at rest are not encrypted by default.

### 2. AWS Config not enabled

**Evidence:** `describe-configuration-recorders` returns an empty list.
**Impact:** no configuration history or compliance rules.

### 3. Single NAT gateway

**Evidence:** one NAT gateway in one AZ.
**Impact:** an AZ failure removes outbound access for private subnets.
