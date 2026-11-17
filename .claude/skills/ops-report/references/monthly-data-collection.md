# Monthly Report: AWS Data Collection Commands

Scope: every AWS CLI command used to collect monthly report data, grouped by service. Run the credential preflight in [monthly-report.md](monthly-report.md) first.

## Identity & Account
```bash
aws sts get-caller-identity --profile <profile>
```

## Cost — Monthly + MoM
```bash
aws ce get-cost-and-usage \
  --time-period Start=<prev_month_start>,End=<period_end> \
  --granularity MONTHLY --metrics UnblendedCost --profile <profile>
```

## Cost — Daily Trend
```bash
aws ce get-cost-and-usage \
  --time-period Start=<period_start>,End=<period_end> \
  --granularity DAILY --metrics UnblendedCost --profile <profile>
```

## Cost — By Service (Top 10 + MoM)
```bash
# Current month
aws ce get-cost-and-usage \
  --time-period Start=<period_start>,End=<period_end> \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE --profile <profile>

# Previous month (for per-service MoM delta)
aws ce get-cost-and-usage \
  --time-period Start=<prev_month_start>,End=<period_start> \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE --profile <profile>
```

## Cost Anomaly Detection
```bash
aws ce get-anomalies \
  --date-interval Start=<period_start>,End=<period_end> \
  --profile <profile>
```

## Budget
```bash
aws budgets describe-budgets --account-id <account_id> --profile <profile> --region us-east-1
```

## Personal Health Dashboard
```bash
# Requires Business/Enterprise Support
aws health describe-events \
  --filter eventStatusCodes=open,upcoming \
  --profile <profile> --region us-east-1

# If SubscriptionRequiredException → note visibility limitation
```

## Security
```bash
aws securityhub describe-hub --profile <profile> --region <region>
aws securityhub get-findings --filters '{"RecordState":[{"Value":"ACTIVE","Comparison":"EQUALS"}]}' --profile <profile> --region <region>
aws guardduty list-detectors --profile <profile> --region <region>
aws cloudtrail describe-trails --include-shadow-trails --profile <profile> --region <region>
```

## Utilization — Compute (EC2)
```bash
aws ec2 describe-instances --profile <profile> --region <region>
aws compute-optimizer get-enrollment-status --profile <profile> --region <region>
aws compute-optimizer get-ec2-instance-recommendations --profile <profile> --region <region>
```

## Utilization — Database (RDS)
```bash
aws rds describe-db-instances --profile <profile> --region <region>

# CPU utilization (period month, 1-day granularity)
aws cloudwatch get-metric-statistics --namespace AWS/RDS \
  --metric-name CPUUtilization --dimensions Name=DBInstanceIdentifier,Value=<db-id> \
  --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 86400 --statistics Average Maximum --profile <profile> --region <region>

# Database connections
aws cloudwatch get-metric-statistics --namespace AWS/RDS \
  --metric-name DatabaseConnections --dimensions Name=DBInstanceIdentifier,Value=<db-id> \
  --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 86400 --statistics Average Maximum --profile <profile> --region <region>

# Free storage space
aws cloudwatch get-metric-statistics --namespace AWS/RDS \
  --metric-name FreeStorageSpace --dimensions Name=DBInstanceIdentifier,Value=<db-id> \
  --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 86400 --statistics Minimum --profile <profile> --region <region>
```

## Utilization — Cache (ElastiCache)
```bash
aws elasticache describe-cache-clusters --show-cache-node-info --profile <profile> --region <region>

# CPU
aws cloudwatch get-metric-statistics --namespace AWS/ElastiCache \
  --metric-name CPUUtilization --dimensions Name=CacheClusterId,Value=<cluster-id> \
  --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 86400 --statistics Average Maximum --profile <profile> --region <region>

# Memory usage
aws cloudwatch get-metric-statistics --namespace AWS/ElastiCache \
  --metric-name DatabaseMemoryUsagePercentage --dimensions Name=CacheClusterId,Value=<cluster-id> \
  --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 86400 --statistics Average Maximum --profile <profile> --region <region>

# Evictions
aws cloudwatch get-metric-statistics --namespace AWS/ElastiCache \
  --metric-name Evictions --dimensions Name=CacheClusterId,Value=<cluster-id> \
  --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 86400 --statistics Sum --profile <profile> --region <region>
```

## Utilization — Load Balancer (ELB)
```bash
# ALB/NLB
aws elbv2 describe-load-balancers --profile <profile> --region <region>
aws elbv2 describe-target-groups --profile <profile> --region <region>
aws elbv2 describe-target-health --target-group-arn <tg-arn> --profile <profile> --region <region>

# Request count (ALB)
aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB \
  --metric-name RequestCount --dimensions Name=LoadBalancer,Value=<lb-id> \
  --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 86400 --statistics Sum --profile <profile> --region <region>

# 5xx errors
aws cloudwatch get-metric-statistics --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_ELB_5XX_Count --dimensions Name=LoadBalancer,Value=<lb-id> \
  --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 86400 --statistics Sum --profile <profile> --region <region>
```

## Utilization — Container (EKS/ECS)
```bash
# EKS
aws eks list-clusters --profile <profile> --region <region>
aws eks describe-cluster --name <cluster> --profile <profile> --region <region>
aws eks list-nodegroups --cluster-name <cluster> --profile <profile> --region <region>
aws eks describe-nodegroup --cluster-name <cluster> --nodegroup-name <ng> --profile <profile> --region <region>

# ECS
aws ecs list-clusters --profile <profile> --region <region>
aws ecs describe-clusters --clusters <cluster-arn> --include STATISTICS --profile <profile> --region <region>
```

## Utilization — Storage (S3/EBS/EFS)
```bash
# EBS volumes (unattached)
aws ec2 describe-volumes --filters Name=status,Values=available --profile <profile> --region <region> \
  --query "Volumes[*].{ID:VolumeId,Size:Size,Type:VolumeType}"

# S3 bucket list
aws s3api list-buckets --profile <profile>

# EFS
aws efs describe-file-systems --profile <profile> --region <region>
```

## Utilization — Serverless (Lambda, if present)
```bash
aws lambda list-functions --profile <profile> --region <region> --query "Functions[*].{Name:FunctionName,Runtime:Runtime,Memory:MemorySize}"

# Invocations + errors (aggregate)
aws cloudwatch get-metric-statistics --namespace AWS/Lambda \
  --metric-name Invocations --start-time <period_start>T00:00:00Z --end-time <period_end>T00:00:00Z \
  --period 2592000 --statistics Sum --profile <profile> --region <region>
```

## Reliability Checks
```bash
# RDS Multi-AZ
aws rds describe-db-instances --profile <profile> --region <region> \
  --query "DBInstances[*].{ID:DBInstanceIdentifier,MultiAZ:MultiAZ,BackupRetention:BackupRetentionPeriod}"

# EBS Snapshots (backup)
aws ec2 describe-snapshots --owner-ids self --profile <profile> --region <region> \
  --query "length(Snapshots)"

# Auto Scaling
aws autoscaling describe-auto-scaling-groups --profile <profile> --region <region> \
  --query "length(AutoScalingGroups)"
```

## Sustainability Checks
```bash
# Instance generations (check for previous-gen)
aws ec2 describe-instances --profile <profile> --region <region> \
  --query "Reservations[*].Instances[*].InstanceType"
# Flag: t2/m4/c4/r4 = previous gen → recommend upgrade to t3/m6i/c6i/r6i or Graviton
```

