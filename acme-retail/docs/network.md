# Network - Acme Retail

| Item | Value |
|------|-------|
| VPC | 10.20.0.0/16 |
| Public subnets | 10.20.0.0/24, 10.20.1.0/24 (ALB, NAT) |
| Private subnets | 10.20.10.0/24, 10.20.11.0/24 (ECS) |
| Data subnets | 10.20.20.0/24, 10.20.21.0/24 (RDS) |
| NAT gateway | 1 (single AZ, see finding F-04) |

## Security groups

| SG | Inbound | Source |
|----|---------|--------|
| alb-sg | 443 | 0.0.0.0/0 |
| api-sg | 8080 | alb-sg |
| db-sg | 5432 | api-sg |
