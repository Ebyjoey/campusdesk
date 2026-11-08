variable "region" {
  description = "AWS region. Mumbai is the closest to SRM."
  type        = string
  default     = "ap-south-1"
}

variable "my_ip_cidr" {
  description = "Your public IP as a /32, for SSH and the Jenkins UI. Example: 203.0.113.7/32"
  type        = string

  validation {
    condition     = can(cidrhost(var.my_ip_cidr, 0)) && endswith(var.my_ip_cidr, "/32")
    error_message = "my_ip_cidr must be a single address ending in /32, for example 203.0.113.7/32."
  }
}

variable "app_cidr" {
  description = "Who may open the application on NodePort 30080. Use your /32 while testing; 0.0.0.0/0 for a public demo."
  type        = string
  default     = "0.0.0.0/0"
}

variable "public_key_path" {
  description = "Path to the SSH public key to register as the EC2 key pair."
  type        = string
  default     = "~/.ssh/campusdesk.pub"
}

variable "key_name" {
  description = "Name of the EC2 key pair created in AWS."
  type        = string
  default     = "campusdesk"
}

variable "enable_nat" {
  description = "Create a NAT gateway so the private database host can install packages. It bills hourly; keep false otherwise."
  type        = bool
  default     = false
}

variable "alert_email" {
  description = "Email address that receives CloudWatch alarm notifications."
  type        = string
}

variable "jenkins_instance_type" {
  type    = string
  default = "t3.small"
}

variable "master_instance_type" {
  type    = string
  default = "t3.small"
}

variable "worker_instance_type" {
  description = "t3.medium is not on the new AWS Free plan. If AWS refuses it, use t3.small."
  type        = string
  default     = "t3.medium"
}

variable "db_instance_type" {
  type    = string
  default = "t3.micro"
}
