# Instances - Acme Retail

| Resource | Type | Name | Notes |
|----------|------|------|-------|
| ECS service | Fargate | acme-api | 3 tasks, behind ALB |
| RDS | db.m6g.large PostgreSQL 15 | acme-prod-db | Multi-AZ, 7-day backup |
| EC2 | t3.small | acme-bastion | Admin access via SSM only |
| S3 | bucket | acme-prod-assets | Static assets, CloudFront origin |
| S3 | bucket | acme-prod-uploads | Customer uploads (finding F-02) |
