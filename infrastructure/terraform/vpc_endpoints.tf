# VPC Endpoints for private AWS service access

# S3 Gateway Endpoint
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = [aws_route_table.private.id]

  tags = {
    Name = "${var.project_name}-${var.environment}-s3-endpoint"
  }
}

# Secrets Manager Interface Endpoint
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type = "Interface"

  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.ecs.id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project_name}-${var.environment}-secretsmanager-endpoint"
  }
}

# STS Interface Endpoint
resource "aws_vpc_endpoint" "sts" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.sts"
  vpc_endpoint_type = "Interface"

  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.ecs.id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project_name}-${var.environment}-sts-endpoint"
  }
}
