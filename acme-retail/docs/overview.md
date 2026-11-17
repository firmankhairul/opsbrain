# Overview - Acme Retail

> Fictional customer. Every ID, address and name here is an example.

- **Account ID:** 123456789012
- **Profile:** `acme-retail`
- **Region:** ap-southeast-1
- **VPC CIDR:** 10.20.0.0/16

## Description

Acme Retail runs an online storefront. Traffic enters through CloudFront and an
Application Load Balancer, reaches an ECS service for the API, and stores data
in an RDS PostgreSQL database and S3 buckets.

## Work streams

- First assessment (2026-11-03)
- Well-Architected Framework Review (2026-11-10)
- Remediation of WAFR findings (issue #1)
