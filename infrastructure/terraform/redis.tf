# ElastiCache Redis

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project_name}-${var.environment}-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

# KMS key for Redis encryption
resource "aws_kms_key" "redis" {
  description             = "KMS key for ElastiCache at-rest encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-${var.environment}-redis-kms-key"
  }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-${var.environment}-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 2
  parameter_group_name = "default.redis7"
  port                 = 6379

  # At-rest encryption
  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.redis.arn

  # Replication group for failover
  engine_version         = "7.0"
  multi_az_enabled       = true
  automatic_failover_enabled = true

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  tags = {
    Name = "${var.project_name}-${var.environment}-redis"
  }
}
