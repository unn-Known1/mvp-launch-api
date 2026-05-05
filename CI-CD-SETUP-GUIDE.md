# CI/CD Pipeline Setup Guide

## Overview
The GitHub Actions workflow (`.github/workflows/ci-cd.yml`) has been configured with all required components. This guide covers the remaining manual setup steps to fully activate the pipeline.

## Completed (In Repository)
- [x] Lint job (flake8, mypy, black, isort)
- [x] Test job (pytest with PostgreSQL + Redis services)
- [x] Security scanning (bandit, pip-audit, CodeQL, Trivy)
- [x] Docker build and ECR push
- [x] Staging deployment job
- [x] Production deployment job
- [x] Rollback jobs for both environments

## Manual Setup Required

### 1. GitHub Environments Setup

Navigate to **Settings → Environments** in your GitHub repository and create:

#### Staging Environment
- **Name**: `staging`
- **Protection rules**:
  - Required reviewers: Add team leads/DevOps engineers
  - Wait timer: 0 minutes (optional)
  - Deployment branches: `develop` only

#### Production Environment
- **Name**: `production`
- **Protection rules**:
  - Required reviewers: Add minimum 2 reviewers for production changes
  - Wait timer: 5-10 minutes (recommended for cooling-off period)
  - Deployment branches: `main` only

### 2. GitHub Secrets Configuration

Add the following secrets in **Settings → Secrets and variables → Actions → Secrets**:

| Secret Name | Description | Where to get |
|------------|-------------|--------------|
| `AWS_ACCESS_KEY_ID` | AWS access key for ECR/ECS deployments | AWS IAM Console |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key paired with access key | AWS IAM Console |

**Steps to create AWS credentials:**
1. Go to AWS IAM Console → Users → Create User
2. Attach policy: `AmazonECS_FullAccess`, `AmazonEC2ContainerRegistryFullAccess`
3. Create access key → Use for GitHub secrets

### 3. AWS Infrastructure Setup

#### ECR Repository
```bash
aws ecr create-repository --repository-name mvp-launch-backend --region us-east-1
```

#### ECS Resources (if not using Terraform)
The `infrastructure/terraform/` directory contains Terraform configs. To deploy:

```bash
cd infrastructure/terraform
terraform init
terraform plan
terraform apply
```

This creates:
- VPC with public/private subnets
- ECS cluster (`mvp-launch-cluster`)
- ECS services (`mvp-launch-service`, `mvp-launch-service-staging`)
- ECR repository
- RDS PostgreSQL instance
- Redis ElastiCache
- Application Load Balancer
- CloudWatch logging

#### ECS Task Definitions

Create task definitions that the CI/CD references:

**Staging task definition** (`mvp-launch-staging`):
```bash
aws ecs register-task-definition --cli-input-json file://infrastructure/task-def-staging.json
```

**Production task definition** (`mvp-launch-prod`):
```bash
aws ecs register-task-definition --cli-input-json file://infrastructure/task-def-prod.json
```

### 4. Branch Protection Rules

Navigate to **Settings → Branches → Add branch protection rule**:

#### For `main` branch:
- [x] Require pull request reviews before merging (2 reviewers)
- [x] Require status checks to pass before merging
  - Required checks: `lint`, `test`, `security-scan`, `build`
- [x] Require branches to be up to date before merging
- [x] Include administrators (optional)

#### For `develop` branch:
- [x] Require pull request reviews before merging (1 reviewer)
- [x] Require status checks to pass before merging
  - Required checks: `lint`, `test`, `security-scan`
- [x] Allow force pushes (optional, for development)

### 5. Verify Pipeline

After setup, trigger the pipeline:

```bash
# Push to develop (triggers staging deployment)
git push origin develop

# Push to main (triggers production deployment)
git push origin main
```

### 6. Rollback Testing

Test rollback functionality:

1. Go to **Actions → CI/CD Pipeline → Run workflow**
2. Select branch
3. Check `rollback_staging` or `rollback_production`
4. Click **Run workflow**

## Pipeline Flow Summary

```
┌─────────┐     ┌─────────┐     ┌──────────────┐     ┌──────────┐
│  lint   │────▶│  test   │────▶│security-scan │────▶│  build   │
└─────────┘     └─────────┘     └──────────────┘     └────┬─────┘
                                                         │
                                    ┌────────────────────┘
                                    │
                          ┌─────────▼─────────┐
                          │                    │
                    ┌─────▼─────┐      ┌─────▼─────┐
                    │deploy-stg │      │deploy-prod │
                    │(develop)  │      │  (main)    │
                    └───────────┘      └────────────┘
```

## Security Features
- **Bandit**: Static analysis for common security issues in Python
- **pip-audit**: Scans dependencies for known vulnerabilities
- **CodeQL**: Deep semantic code analysis by GitHub
- **Trivy**: Container image vulnerability scanning

## Troubleshooting

| Issue | Solution |
|-------|----------|
| ECR login fails | Verify AWS secrets are correct |
| Task definition not found | Run Terraform or manually create task definitions |
| Tests fail with DB connection | Check if PostgreSQL service health check passes |
| Deployment timeout | Increase `wait-for-service-stability` timeout or check ECS service health |
