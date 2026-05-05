# Performance Requirements - FOR-27

## 1. API Performance Targets

### 1.1 Latency SLAs
| Operation Type          | Target (p95) | Target (p99) | Measurement      |
|-------------------------|--------------|--------------|------------------|
| Simple read             | 50ms         | 100ms        | API Gateway      |
| Complex read (joins)    | 150ms        | 300ms        | API Gateway      |
| Write (single record)   | 100ms        | 200ms        | API Gateway      |
| Bulk import (1000 rows) | 5s           | 10s          | End-to-end       |
| ML forecast (small)     | 500ms        | 1s           | API Gateway      |
| ML forecast (large)     | 10s          | 30s          | Background job   |
| NLP analysis            | 200ms        | 500ms        | API Gateway      |

### 1.2 Throughput Limits
| Endpoint Category      | Rate Limit     | Burst Limit    |
|-----------------------|----------------|----------------|
| Authentication        | 100 req/min    | 200            |
| Data reads            | 1000 req/min   | 2000           |
| Data writes           | 200 req/min    | 400            |
| ML endpoints          | 50 req/min     | 100            |
| Bulk imports          | 5 req/min      | 10             |
| File uploads          | 10 req/min     | 20             |

### 1.3 Concurrent Users
- **MVP Target**: 100 concurrent users
- **Scale Target**: 1000 concurrent users (future)

## 2. Database Performance

### 2.1 PostgreSQL (RDS)
| Metric                    | Target        | Alert Threshold  |
|---------------------------|---------------|------------------|
| Connection pool size      | 20-50         | >80% utilization |
| Query latency (avg)       | <50ms         | >200ms           |
| Query latency (p99)       | <200ms        | >500ms           |
| Disk I/O                  | <50%          | >80%             |
| CPU utilization           | <70%          | >90%             |
| Memory utilization         | <80%          | >90%             |
| Replication lag           | <100ms        | >500ms           |

### 2.2 Indexing Strategy
- Primary keys: UUID with btree
- Foreign keys: btree indexes
- Date ranges: btree with range partitioning
- JSON queries: GIN indexes
- Full-text search: pg_trgm extension

### 2.3 Connection Management
- PgBouncer for connection pooling
- Max 50 connections per ECS task
- Idle timeout: 60 seconds
- Statement timeout: 30 seconds

## 3. Frontend Performance

### 3.1 Page Load Metrics
| Metric                      | Target      |
|-----------------------------|-------------|
| First Contentful Paint     | <1.0s       |
| Largest Contentful Paint   | <2.0s       |
| Time to Interactive        | <3.0s       |
| Cumulative Layout Shift    | <0.1        |
| Total bundle size          | <500KB      |

### 3.2 React Optimization
- Code splitting per route
- Lazy loading for D3.js components
- Memoization for expensive computations
- Virtual scrolling for large data tables
- SWR/React Query for data fetching

### 3.3 Caching Strategy
- Static assets: CloudFront CDN (1 year)
- API responses: Redis (short TTL)
- D3.js visualizations: IndexedDB cache

## 4. ML Performance

### 4.1 Prophet Forecasting
| Dataset Size | Target Latency | Memory Limit |
|-------------|----------------|--------------|
| <10K rows   | <5s            | 1GB          |
| 10K-100K    | <30s           | 2GB          |
| >100K       | <2min (async)  | 4GB          |

### 4.2 NLP Processing
| Operation      | Target Latency |
|----------------|----------------|
| Sentiment      | <200ms         |
| Entity extract | <300ms         |
| Keyword extract| <250ms         |
| Text summary   | <500ms         |

### 4.3 Model Caching
- Cached predictions: 1 hour TTL
- Model hot-reload without downtime
- Fallback to cached results on failure

## 5. Infrastructure Performance

### 5.1 Auto-Scaling Rules
| Service   | Metric              | Scale Up | Scale Down |
|-----------|---------------------|----------|------------|
| ECS       | CPU >70%            | +2 tasks | -          |
| ECS       | Memory >80%         | +2 tasks | -          |
| ECS       | Request count >1000 | +1 task  | -          |
| Lambda    | Concurrency 80%    | +100     | -          |
| RDS       | Connections 80%    | Alert    | -          |

### 5.2 Capacity Planning
| Resource      | MVP Capacity   | Scale Capacity |
|---------------|----------------|-----------------|
| ECS tasks     | 4 (min 2)     | 20 (max)        |
| RDS instance  | db.t3.medium   | db.r5.large     |
| S3 storage    | 100GB          | 1TB             |
| CloudFront    | 100GB/month    | 1TB/month       |

### 5.3 Availability Targets
| Metric              | Target    |
|---------------------|-----------|
| Uptime (monthly)    | 99.9%     |
| Error rate          | <0.1%     |
| Recovery time (MTTR)| <15 min   |
| Deployment time     | <5 min    |

## 6. Monitoring & Alerts

### 6.1 Key Metrics Dashboard
- API latency (p50, p95, p99)
- Error rate by endpoint
- Active users
- Database query performance
- ML job queue depth
- ECS task count and health

### 6.2 Alert Thresholds
| Alert Type        | Threshold           | Notification |
|-------------------|---------------------|--------------|
| High error rate   | >1% for 5 min       | PagerDuty    |
| High latency      | p95 >500ms for 5min| Slack        |
| Low availability  | <99.5% for 5 min   | PagerDuty    |
| Queue backlog     | >100 jobs           | Slack        |
| Disk space        | >80%                | Slack        |
| Failed deployments| Any                 | PagerDuty    |

## Performance Verification
- [x] API latency targets defined
- [x] Throughput limits specified
- [x] Database performance baselines
- [x] Frontend load time targets
- [x] ML inference SLAs
- [x] Auto-scaling rules configured
- [x] Availability targets set
- [x] Monitoring dashboard planned