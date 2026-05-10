# Terraform Infrastructure for MVP Launch

## Overview

This directory contains Terraform configurations for the MVP Launch AWS infrastructure, including:

- VPC with public/private subnets across 2 AZs
- ECS Fargate cluster for containerized backend
- RDS PostgreSQL database
- ElastiCache Redis cluster
- Application Load Balancer (ALB)
- CloudFront CDN
- ECR repository for Docker images
- S3 bucket for data storage
- Secrets Manager for database credentials
- CloudWatch logging and dashboards
- Datadog integration (optional)

## Environments

- **staging** — `terraform.tfvars.staging`
- **production** — `terraform.tfvars.production`

## Quick Start

```bash
cd infrastructure/terraform

# Initialize Terraform (first time only)
terraform init

# Validate configuration
terraform validate

# Plan for staging
terraform plan -var-file=terraform.tfvars.staging -out=tfplan

# Apply to staging
terraform apply tfplan

# Plan for production
terraform plan -var-file=terraform.tfvars.production -out=tfplan

# Apply to production
terraform apply tfplan
```

## Backend State

Terraform state is stored in S3 with DynamoDB locking. You must create the state bucket and lock table first:

```bash
aws s3 mb s3://mvp-launch-terraform-state --region us-east-1
aws dynamodb create-table \
  --table-name mvp-launch-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Important Notes

- **db_password** in tfvars files must be changed to strong passwords before applying
- **datadog_api_key** is optional — leave empty to skip Datadog setup
- Production uses multi-AZ RDS, deletion protection, and 7-day backup retention
- Staging uses single-AZ RDS with faster iteration cycles

## Outputs

After `terraform apply`, key outputs include:

- `vpc_id` — VPC ID
- `alb_dns_name` — ALB DNS name for CloudFront origin
- `ecr_repository_url` — ECR repo URL for CI/CD pushes
- `rds_endpoint` — PostgreSQL endpoint (sensitive)
- `redis_endpoint` — Redis endpoint
- `s3_bucket_name` — Data bucket name
