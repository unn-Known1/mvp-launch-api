# Terraform configuration for MVP Launch AWS Infrastructure
# Main provider configuration
# Note: terraform block is in versions.tf

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "mvp-launch"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}
