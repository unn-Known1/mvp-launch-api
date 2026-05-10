# Security Architecture - FOR-27

## 1. Authentication

### 1.1 JWT Implementation
- **Access Tokens**: 15-minute expiry, stored in memory
- **Refresh Tokens**: 7-day expiry, HTTP-only secure cookie
- **Signing Algorithm**: RS256 with RSA keys
- **Key Rotation**: Automatic every 90 days via AWS Secrets Manager

### 1.2 OAuth 2.0 Integration
- Provider: Auth0 or AWS Cognito
- Supported flows: Authorization Code + PKCE for SPA
- Scopes: `openid`, `profile`, `email`

### 1.3 Password Security
- Algorithm: bcrypt with cost factor 12
- Minimum length: 12 characters
- Complexity requirements: uppercase, lowercase, number, special char
- Rate limiting: 5 attempts per minute per IP

## 2. Authorization (RBAC)

### 2.1 Role Definitions
```
| Role     | Permissions                                                   |
|----------|---------------------------------------------------------------|
| admin    | Full system access, user management, audit logs, settings  |
| analyst  | Create/manage datasets, run ML models, create forecasts   |
| viewer   | Read-only access to own datasets and forecasts             |
```

### 2.2 Permission Matrix
| Resource   | admin | analyst | viewer |
|------------|-------|---------|--------|
| users      | CRUD  | read    | -      |
| datasets   | CRUD  | CRUD    | read   |
| forecasts  | CRUD  | CRUD    | read   |
| ml/analyze | yes   | yes     | -      |
| admin      | yes   | -       | -      |

### 2.3 Implementation
- Permissions checked at API endpoint level via FastAPI dependencies
- Resource-level access control in service layer
- Audit logging for all access and mutations

## 3. Data Encryption

### 3.1 Encryption at Rest
- **Database (RDS)**: AWS-managed KMS keys, AES-256
- **S3 Buckets**: Server-side encryption with KMS (SSE-KMS)
- **Backup**: Encrypted snapshots, retained 30 days
- **Redis**: TLS encryption in transit (ElastiCache)

### 3.2 Encryption in Transit
- **All traffic**: TLS 1.3 mandatory
- **Certificate**: ACM with auto-renewal
- **HSTS**: Enabled with 1-year max-age
- **API Gateway**: WAF with rate limiting

### 3.3 Application-Level
- Sensitive fields in DB: AES-256 encrypted (user PII)
- Field-level encryption keys: Separate from data keys

## 4. Credential Management

### 4.1 Secrets Storage
- **AWS Secrets Manager** for all secrets
- Secrets encrypted with dedicated KMS key per environment
- Automatic rotation: 30-day intervals for DB credentials

### 4.2 Secrets List
| Secret Name              | Rotation | Description              |
|--------------------------|----------|--------------------------|
| db-master-credentials    | 30 days  | PostgreSQL connection    |
| jwt-signing-key          | 90 days  | JWT token signing        |
| api-keys                 | manual   | Third-party API keys    |
| s3-bucket-keys           | 90 days  | S3 access credentials    |

### 4.3 Application Access
- Credentials injected at container startup via ECS secrets
- No hardcoded credentials in source code
- Environment variables only in local development

## 5. Network Security

### 5.1 VPC Architecture
```
┌──────────────────────────────────────────┐
│           Public Subnet (ALB)            │
│         10.0.1.0/24 - az1               │
│         10.0.2.0/24 - az2               │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────┴───────────────────────┐
│          Private Subnet (ECS)            │
│        10.0.10.0/24 - az1               │
│        10.0.20.0/24 - az2               │
│  - FastAPI containers                    │
│  - No direct internet access             │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────┴───────────────────────┐
│          Private Subnet (Data)           │
│        10.0.30.0/24 - az1               │
│        10.0.40.0/24 - az2               │
│  - RDS PostgreSQL                        │
│  - ElastiCache Redis                     │
└──────────────────────────────────────────┘
```

### 5.2 Security Groups
- **ALB SG**: Allow 443 from 0.0.0.0/0
- **ECS SG**: Allow 8000 from ALB SG only
- **RDS SG**: Allow 5432 from ECS SG only
- **Redis SG**: Allow 6379 from ECS SG only

### 5.3 Additional Controls
- WAF rules: SQL injection, XSS, geo-blocking
- VPN/PrivateLink for admin access
- VPC Flow Logs enabled for monitoring

## 6. Monitoring & Incident Response

### 6.1 Security Monitoring
- CloudTrail: All API calls logged
- GuardDuty: Threat detection enabled
- Security Hub: Centralized findings
- Custom: Failed auth attempts, unusual patterns

### 6.2 Incident Response
1. **Detection**: Automated alerts via CloudWatch
2. **Containment**: Auto-scale blocking, IP blocking
3. **Eradication**: Secret rotation procedures
4. **Recovery**: Backup restoration procedure
5. **Post-mortem**: 48-hour report requirement

### 6.3 Compliance
- Data retention: 90 days for logs, configurable per data type
- PII handling: GDPR-compliant deletion
- Access reviews: Quarterly for admin role

## Security Checklist
- [x] JWT authentication with short-lived tokens
- [x] RBAC with role-based permissions
- [x] TLS 1.3 for all communications
- [x] Encryption at rest (RDS, S3)
- [x] Secrets management (AWS Secrets Manager)
- [x] VPC with private subnets
- [x] Security groups with least privilege
- [x] WAF protection
- [x] Audit logging
- [x] Incident response plan