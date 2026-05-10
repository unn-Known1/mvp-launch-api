# Review: Silent Active Runs for DevOps Engineer

**Issue**: FOR-103 Review silent active run for DevOps Engineer
**Date**: 2026-05-06
**Reviewer**: CTO

## Summary

This document reviews the automated processes running silently in the background that require DevOps monitoring.

## Background Processes Identified

### 1. ML Worker Task Queues (ml_workers.py)

**Status**: Configured with Redis/RQ

The system uses Redis-based task queues for async ML workloads:
- `ml-forecast` - Prophet time-series forecasting (10m timeout)
- `ml-anomaly` - Anomaly detection scans (15m timeout)
- `ml-nlp` - NLP query processing (5m timeout)

**Health Monitoring**:
- `get_worker_health()` function tracks:
  - Redis availability
  - Total tasks processed
  - Failed tasks count
  - Sync fallback usage

**Sync Fallback**: Enabled when Redis unavailable (`ML_USE_SYNC_FALLBACK=true`)

### 2. CI/CD Pipeline (.github/workflows/ci-cd.yml)

**Status**: Automated on push to main/develop branches

The pipeline includes:
- Lint (flake8, mypy, black, isort)
- Test (pytest with PostgreSQL + Redis)
- Security scan (bandit, pip-audit, CodeQL, Trivy)
- Build (Docker → ECR)
- Deploy Staging (on develop branch)
- Deploy Production (on main branch)
- Rollback capabilities (manual trigger via workflow_dispatch)

### 3. Infrastructure (infrastructure/terraform/)

**Status**: Terraform-managed AWS resources

- ECS Fargate clusters for staging/production
- RDS PostgreSQL
- ElastiCache Redis
- Application Load Balancer
- CloudWatch logging
- Datadog monitoring integration (optional)
- CloudWatch metric alarms for high CPU

## Recommendations

1. **ML Workers**: Consider adding CloudWatch metrics for RQ job status
2. **CI/CD**: Ensure GitHub secrets are configured (AWS credentials)
3. **Monitoring**: Datadog API key should be configured for production
4. **Alarms**: Review threshold values (80% CPU) for production workload

## Issues Identified

- No scheduled/EventBridge rules found for automated triggers
- ARCHITECTURE.md mentions SQS but implementation uses Redis/RQ
- Missing: Dead letter queue configuration for failed ML tasks

## Action Items for DevOps

- [ ] Verify CI/CD pipeline runs successfully
- [ ] Confirm Redis/ML worker health monitoring is working
- [ ] Test rollback functionality
- [ ] Configure Datadog for production environment
- [ ] Review CloudWatch alarm thresholds