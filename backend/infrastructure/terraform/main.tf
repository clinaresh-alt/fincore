# ============================================================================
# FinCore - Terraform Infrastructure
# Multi-Region Disaster Recovery Setup
# ============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Backend remoto para estado compartido
  backend "s3" {
    bucket         = "fincore-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "fincore-terraform-locks"
  }
}

# ============================================================================
# Providers
# ============================================================================

# Region primaria
provider "aws" {
  region = var.primary_region

  default_tags {
    tags = {
      Project     = "FinCore"
      Environment = var.environment
      ManagedBy   = "Terraform"
      CostCenter  = "Platform"
    }
  }
}

# Region DR (secundaria)
provider "aws" {
  alias  = "dr"
  region = var.dr_region

  default_tags {
    tags = {
      Project     = "FinCore"
      Environment = "${var.environment}-dr"
      ManagedBy   = "Terraform"
      CostCenter  = "Platform"
    }
  }
}

# ============================================================================
# Data Sources
# ============================================================================

data "aws_availability_zones" "primary" {
  state = "available"
}

data "aws_availability_zones" "dr" {
  provider = aws.dr
  state    = "available"
}

data "aws_caller_identity" "current" {}

# ============================================================================
# Random Resources
# ============================================================================

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_id" "suffix" {
  byte_length = 4
}

# ============================================================================
# VPC - Primary Region
# ============================================================================

module "vpc_primary" {
  source = "./modules/vpc"

  name               = "fincore-${var.environment}"
  cidr               = var.vpc_cidr_primary
  availability_zones = slice(data.aws_availability_zones.primary.names, 0, 3)

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production"
  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC Flow Logs
  enable_flow_logs          = true
  flow_logs_retention_days  = 30

  tags = {
    Region = var.primary_region
    Type   = "Primary"
  }
}

# ============================================================================
# VPC - DR Region
# ============================================================================

module "vpc_dr" {
  source = "./modules/vpc"

  providers = {
    aws = aws.dr
  }

  name               = "fincore-${var.environment}-dr"
  cidr               = var.vpc_cidr_dr
  availability_zones = slice(data.aws_availability_zones.dr.names, 0, 3)

  enable_nat_gateway   = true
  single_nat_gateway   = true  # Ahorro de costos en DR
  enable_dns_hostnames = true
  enable_dns_support   = true

  enable_flow_logs         = true
  flow_logs_retention_days = 30

  tags = {
    Region = var.dr_region
    Type   = "DR"
  }
}

# ============================================================================
# VPC Peering entre regiones
# ============================================================================

resource "aws_vpc_peering_connection" "primary_to_dr" {
  vpc_id      = module.vpc_primary.vpc_id
  peer_vpc_id = module.vpc_dr.vpc_id
  peer_region = var.dr_region
  auto_accept = false

  tags = {
    Name = "fincore-primary-to-dr"
    Side = "Requester"
  }
}

resource "aws_vpc_peering_connection_accepter" "dr" {
  provider                  = aws.dr
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_dr.id
  auto_accept               = true

  tags = {
    Name = "fincore-primary-to-dr"
    Side = "Accepter"
  }
}

# ============================================================================
# RDS - Primary Region (Multi-AZ)
# ============================================================================

module "rds_primary" {
  source = "./modules/rds"

  identifier = "fincore-${var.environment}"

  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = var.db_instance_class
  allocated_storage    = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage

  db_name  = "fincore"
  username = "fincore_admin"
  password = random_password.db_password.result

  vpc_id          = module.vpc_primary.vpc_id
  subnet_ids      = module.vpc_primary.private_subnet_ids
  allowed_cidrs   = [var.vpc_cidr_primary, var.vpc_cidr_dr]

  # Alta disponibilidad
  multi_az               = var.environment == "production"
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"

  # Seguridad
  storage_encrypted   = true
  deletion_protection = var.environment == "production"

  # Performance Insights
  performance_insights_enabled = true
  performance_insights_retention_period = 7

  # Logs
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Region = var.primary_region
    Type   = "Primary"
  }
}

# ============================================================================
# RDS - DR Region (Read Replica)
# ============================================================================

module "rds_dr" {
  source = "./modules/rds"

  providers = {
    aws = aws.dr
  }

  identifier = "fincore-${var.environment}-dr"

  # Configurar como replica
  replicate_source_db = module.rds_primary.db_instance_arn

  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.db_instance_class_dr

  vpc_id        = module.vpc_dr.vpc_id
  subnet_ids    = module.vpc_dr.private_subnet_ids
  allowed_cidrs = [var.vpc_cidr_dr, var.vpc_cidr_primary]

  multi_az = false  # DR es single-AZ para ahorro

  # La replica hereda encriptacion del source
  storage_encrypted = true

  tags = {
    Region = var.dr_region
    Type   = "DR-Replica"
  }
}

# ============================================================================
# ElastiCache (Redis) - Primary
# ============================================================================

module "elasticache_primary" {
  source = "./modules/elasticache"

  cluster_id = "fincore-${var.environment}"

  engine               = "redis"
  engine_version       = "7.0"
  node_type           = var.redis_node_type
  num_cache_nodes     = var.environment == "production" ? 2 : 1

  vpc_id     = module.vpc_primary.vpc_id
  subnet_ids = module.vpc_primary.private_subnet_ids

  # Cluster mode para HA
  automatic_failover_enabled = var.environment == "production"
  multi_az_enabled          = var.environment == "production"

  # Snapshots
  snapshot_retention_limit = 7
  snapshot_window         = "05:00-06:00"

  # Seguridad
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = {
    Region = var.primary_region
  }
}

# ============================================================================
# ElastiCache (Redis) - DR
# ============================================================================

module "elasticache_dr" {
  source = "./modules/elasticache"

  providers = {
    aws = aws.dr
  }

  cluster_id = "fincore-${var.environment}-dr"

  engine         = "redis"
  engine_version = "7.0"
  node_type     = var.redis_node_type_dr
  num_cache_nodes = 1

  vpc_id     = module.vpc_dr.vpc_id
  subnet_ids = module.vpc_dr.private_subnet_ids

  automatic_failover_enabled = false
  multi_az_enabled          = false

  snapshot_retention_limit = 3
  snapshot_window         = "05:00-06:00"

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = {
    Region = var.dr_region
    Type   = "DR"
  }
}

# ============================================================================
# S3 - Buckets con replicacion cross-region
# ============================================================================

module "s3_primary" {
  source = "./modules/s3"

  bucket_name = "fincore-${var.environment}-${random_id.suffix.hex}"

  versioning_enabled = true

  # Replicacion a DR
  replication_enabled     = true
  replication_destination = module.s3_dr.bucket_arn
  replication_role_arn   = aws_iam_role.s3_replication.arn

  # Lifecycle
  lifecycle_rules = [
    {
      id      = "archive-old-objects"
      enabled = true
      transitions = [
        {
          days          = 90
          storage_class = "STANDARD_IA"
        },
        {
          days          = 365
          storage_class = "GLACIER"
        }
      ]
      noncurrent_version_expiration = {
        days = 90
      }
    }
  ]

  # Encriptacion
  server_side_encryption = "aws:kms"
  kms_key_arn           = aws_kms_key.primary.arn

  tags = {
    Region = var.primary_region
    Type   = "Primary"
  }
}

module "s3_dr" {
  source = "./modules/s3"

  providers = {
    aws = aws.dr
  }

  bucket_name = "fincore-${var.environment}-dr-${random_id.suffix.hex}"

  versioning_enabled = true

  # Este bucket es destino de replicacion
  replication_enabled = false

  server_side_encryption = "aws:kms"
  kms_key_arn           = aws_kms_key.dr.arn

  tags = {
    Region = var.dr_region
    Type   = "DR-Replica"
  }
}

# ============================================================================
# KMS Keys
# ============================================================================

resource "aws_kms_key" "primary" {
  description             = "FinCore encryption key - Primary"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region           = true

  tags = {
    Name   = "fincore-${var.environment}-primary"
    Region = var.primary_region
  }
}

resource "aws_kms_replica_key" "dr" {
  provider = aws.dr

  description             = "FinCore encryption key - DR Replica"
  primary_key_arn        = aws_kms_key.primary.arn
  deletion_window_in_days = 30

  tags = {
    Name   = "fincore-${var.environment}-dr"
    Region = var.dr_region
  }
}

resource "aws_kms_key" "dr" {
  provider = aws.dr

  description             = "FinCore encryption key - DR"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name   = "fincore-${var.environment}-dr"
    Region = var.dr_region
  }
}

# ============================================================================
# IAM Role for S3 Replication
# ============================================================================

resource "aws_iam_role" "s3_replication" {
  name = "fincore-s3-replication-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "s3_replication" {
  name = "fincore-s3-replication-policy"
  role = aws_iam_role.s3_replication.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Effect = "Allow"
        Resource = [
          module.s3_primary.bucket_arn
        ]
      },
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect = "Allow"
        Resource = [
          "${module.s3_primary.bucket_arn}/*"
        ]
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect = "Allow"
        Resource = [
          "${module.s3_dr.bucket_arn}/*"
        ]
      },
      {
        Action = [
          "kms:Decrypt"
        ]
        Effect = "Allow"
        Resource = [
          aws_kms_key.primary.arn
        ]
      },
      {
        Action = [
          "kms:Encrypt"
        ]
        Effect = "Allow"
        Resource = [
          aws_kms_key.dr.arn
        ]
      }
    ]
  })
}

# ============================================================================
# Route53 Health Checks y DNS Failover
# ============================================================================

resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_endpoint
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  tags = {
    Name = "fincore-primary-health"
  }
}

resource "aws_route53_health_check" "dr" {
  fqdn              = var.dr_endpoint
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 30

  tags = {
    Name = "fincore-dr-health"
  }
}

# ============================================================================
# CloudWatch Alarms para DR
# ============================================================================

resource "aws_cloudwatch_metric_alarm" "db_replication_lag" {
  alarm_name          = "fincore-db-replication-lag"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ReplicaLag"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 60  # segundos
  alarm_description   = "Database replication lag is too high"

  dimensions = {
    DBInstanceIdentifier = module.rds_dr.db_instance_id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_sns_topic" "alerts" {
  name = "fincore-${var.environment}-alerts"
}

# ============================================================================
# Outputs
# ============================================================================

output "vpc_primary_id" {
  description = "VPC ID - Primary Region"
  value       = module.vpc_primary.vpc_id
}

output "vpc_dr_id" {
  description = "VPC ID - DR Region"
  value       = module.vpc_dr.vpc_id
}

output "rds_primary_endpoint" {
  description = "RDS Endpoint - Primary"
  value       = module.rds_primary.db_endpoint
  sensitive   = true
}

output "rds_dr_endpoint" {
  description = "RDS Endpoint - DR Replica"
  value       = module.rds_dr.db_endpoint
  sensitive   = true
}

output "redis_primary_endpoint" {
  description = "Redis Endpoint - Primary"
  value       = module.elasticache_primary.primary_endpoint
}

output "redis_dr_endpoint" {
  description = "Redis Endpoint - DR"
  value       = module.elasticache_dr.primary_endpoint
}

output "s3_primary_bucket" {
  description = "S3 Bucket - Primary"
  value       = module.s3_primary.bucket_name
}

output "s3_dr_bucket" {
  description = "S3 Bucket - DR"
  value       = module.s3_dr.bucket_name
}
