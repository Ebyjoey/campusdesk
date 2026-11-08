resource "aws_key_pair" "main" {
  key_name   = var.key_name
  public_key = file(pathexpand(var.public_key_path))
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Jenkins: 10.20.1.10 (public subnet 1)
resource "aws_instance" "jenkins" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.jenkins_instance_type
  subnet_id              = aws_subnet.public[0].id
  private_ip             = "10.20.1.10"
  vpc_security_group_ids = [aws_security_group.jenkins.id]
  key_name               = aws_key_pair.main.key_name
  iam_instance_profile   = aws_iam_instance_profile.cw.name

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required" # IMDSv2 only
  }

  root_block_device {
    volume_size = 25
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "campusdesk-jenkins", Role = "jenkins" }

  lifecycle { ignore_changes = [ami] } # a newer Ubuntu image must not replace a running host
}

# k3s control plane: 10.20.1.20 (public subnet 1)
resource "aws_instance" "master" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.master_instance_type
  subnet_id              = aws_subnet.public[0].id
  private_ip             = "10.20.1.20"
  vpc_security_group_ids = [aws_security_group.k8s.id]
  key_name               = aws_key_pair.main.key_name
  iam_instance_profile   = aws_iam_instance_profile.cw.name

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "campusdesk-k3s-master", Role = "k3s-master" }

  lifecycle { ignore_changes = [ami] }
}

# k3s worker: 10.20.2.20 (public subnet 2)
resource "aws_instance" "worker" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.worker_instance_type
  subnet_id              = aws_subnet.public[1].id
  private_ip             = "10.20.2.20"
  vpc_security_group_ids = [aws_security_group.k8s.id]
  key_name               = aws_key_pair.main.key_name
  iam_instance_profile   = aws_iam_instance_profile.cw.name

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "campusdesk-k3s-worker", Role = "k3s-worker" }

  lifecycle { ignore_changes = [ami] }
}

# PostgreSQL: 10.20.11.10 (private subnet 1, no public address)
resource "aws_instance" "db" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.db_instance_type
  subnet_id                   = aws_subnet.private[0].id
  private_ip                  = "10.20.11.10"
  associate_public_ip_address = false
  vpc_security_group_ids      = [aws_security_group.db.id]
  key_name                    = aws_key_pair.main.key_name

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = { Name = "campusdesk-db", Role = "db" }

  lifecycle { ignore_changes = [ami] }
}
