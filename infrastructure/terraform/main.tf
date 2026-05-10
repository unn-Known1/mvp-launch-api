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

locals {
  availability_zones = length(var.availability_zones) > 0 ? var.availability_zones : (
    length(data.aws_availability_zones.available) > 0 ? data.aws_availability_zones.available[0].names : ["us-east-1a", "us-east-1b"]
  )
}

data "aws_availability_zones" "available" {
  count = length(var.availability_zones) > 0 ? 0 : 1
  state = "available"
}
