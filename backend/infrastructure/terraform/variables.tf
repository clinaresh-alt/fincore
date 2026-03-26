# ============================================================================
# FinCore - Terraform Variables
# ============================================================================

# ============================================================================
# General
# ============================================================================

variable "environment" {
  description = "Environment name (development, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production."
  }
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "fincore"
}

# ============================================================================
# Regions
# ============================================================================

variable "primary_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-east-1"
}

variable "dr_region" {
  description = "Disaster Recovery AWS region"
  type        = string
  default     = "us-west-2"
}

# ============================================================================
# Networking
# ============================================================================

variable "vpc_cidr_primary" {
  description = "CIDR block for primary VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "vpc_cidr_dr" {
  description = "CIDR block for DR VPC"
  type        = string
  default     = "10.1.0.0/16"
}

# ============================================================================
# Database (RDS)
# ============================================================================

variable "db_instance_class" {
  description = "RDS instance class for primary"
  type        = string
  default     = "db.r6g.large"
}

variable "db_instance_class_dr" {
  description = "RDS instance class for DR replica"
  type        = string
  default     = "db.r6g.medium"
}

variable "db_allocated_storage" {
  description = "Initial allocated storage in GB"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for autoscaling in GB"
  type        = number
  default     = 500
}

# ============================================================================
# Cache (ElastiCache Redis)
# ============================================================================

variable "redis_node_type" {
  description = "ElastiCache node type for primary"
  type        = string
  default     = "cache.r6g.large"
}

variable "redis_node_type_dr" {
  description = "ElastiCache node type for DR"
  type        = string
  default     = "cache.r6g.medium"
}

# ============================================================================
# ECS
# ============================================================================

variable "ecs_task_cpu" {
  description = "CPU units for ECS tasks"
  type        = number
  default     = 1024
}

variable "ecs_task_memory" {
  description = "Memory for ECS tasks in MB"
  type        = number
  default     = 2048
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_min_capacity" {
  description = "Minimum number of ECS tasks for autoscaling"
  type        = number
  default     = 2
}

variable "ecs_max_capacity" {
  description = "Maximum number of ECS tasks for autoscaling"
  type        = number
  default     = 10
}

# ============================================================================
# Endpoints (for health checks)
# ============================================================================

variable "primary_endpoint" {
  description = "Primary region endpoint for health checks"
  type        = string
  default     = "api.fincore.com"
}

variable "dr_endpoint" {
  description = "DR region endpoint for health checks"
  type        = string
  default     = "api-dr.fincore.com"
}

# ============================================================================
# Recovery Objectives
# ============================================================================

variable "rto_minutes" {
  description = "Recovery Time Objective in minutes"
  type        = number
  default     = 60

  validation {
    condition     = var.rto_minutes >= 15 && var.rto_minutes <= 240
    error_message = "RTO must be between 15 and 240 minutes."
  }
}

variable "rpo_minutes" {
  description = "Recovery Point Objective in minutes"
  type        = number
  default     = 15

  validation {
    condition     = var.rpo_minutes >= 1 && var.rpo_minutes <= 60
    error_message = "RPO must be between 1 and 60 minutes."
  }
}

# ============================================================================
# Monitoring
# ============================================================================

variable "enable_enhanced_monitoring" {
  description = "Enable enhanced monitoring for RDS"
  type        = bool
  default     = true
}

variable "monitoring_interval" {
  description = "Enhanced monitoring interval in seconds"
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# ============================================================================
# Tags
# ============================================================================

variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
