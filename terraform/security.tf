# Rules are separate resources (not inline blocks) so the security groups can
# reference each other without a dependency cycle.

resource "aws_security_group" "jenkins" {
  name        = "campusdesk-jenkins-sg"
  description = "Jenkins host"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "campusdesk-jenkins-sg" }
}

resource "aws_security_group" "k8s" {
  name        = "campusdesk-k8s-sg"
  description = "k3s master and worker"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "campusdesk-k8s-sg" }
}

resource "aws_security_group" "db" {
  name        = "campusdesk-db-sg"
  description = "PostgreSQL host"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "campusdesk-db-sg" }
}

# ---------- Jenkins ----------
resource "aws_vpc_security_group_ingress_rule" "jenkins_ssh" {
  security_group_id = aws_security_group.jenkins.id
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  description       = "SSH from my IP"
}

resource "aws_vpc_security_group_ingress_rule" "jenkins_ui" {
  security_group_id = aws_security_group.jenkins.id
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 8080
  to_port           = 8080
  description       = "Jenkins UI from my IP"
}

# ---------- Kubernetes nodes ----------
resource "aws_vpc_security_group_ingress_rule" "k8s_ssh" {
  security_group_id = aws_security_group.k8s.id
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  description       = "SSH from my IP"
}

resource "aws_vpc_security_group_ingress_rule" "k8s_api_from_jenkins" {
  security_group_id            = aws_security_group.k8s.id
  referenced_security_group_id = aws_security_group.jenkins.id
  ip_protocol                  = "tcp"
  from_port                    = 6443
  to_port                      = 6443
  description                  = "kubectl from Jenkins"
}

resource "aws_vpc_security_group_ingress_rule" "k8s_app_public" {
  security_group_id = aws_security_group.k8s.id
  cidr_ipv4         = var.app_cidr
  ip_protocol       = "tcp"
  from_port         = 30080
  to_port           = 30080
  description       = "Application NodePort"
}

resource "aws_vpc_security_group_ingress_rule" "k8s_app_from_jenkins" {
  security_group_id            = aws_security_group.k8s.id
  referenced_security_group_id = aws_security_group.jenkins.id
  ip_protocol                  = "tcp"
  from_port                    = 30080
  to_port                      = 30080
  description                  = "Pipeline smoke test"
}

resource "aws_vpc_security_group_ingress_rule" "k8s_self" {
  security_group_id            = aws_security_group.k8s.id
  referenced_security_group_id = aws_security_group.k8s.id
  ip_protocol                  = "-1"
  description                  = "Node to node: kubelet and pod network"
}

resource "aws_vpc_security_group_ingress_rule" "k8s_node_exporter_from_jenkins" {
  security_group_id            = aws_security_group.k8s.id
  referenced_security_group_id = aws_security_group.jenkins.id
  ip_protocol                  = "tcp"
  from_port                    = 9100
  to_port                      = 9100
  description                  = "Prometheus (on Jenkins host) scrapes node_exporter"
}

# ---------- Database ----------
resource "aws_vpc_security_group_ingress_rule" "db_from_k8s" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = aws_security_group.k8s.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL from Kubernetes nodes only"
}

resource "aws_vpc_security_group_ingress_rule" "db_ssh_from_jenkins" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = aws_security_group.jenkins.id
  ip_protocol                  = "tcp"
  from_port                    = 22
  to_port                      = 22
  description                  = "SSH jump through the Jenkins host"
}

resource "aws_vpc_security_group_ingress_rule" "db_node_exporter" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = aws_security_group.jenkins.id
  ip_protocol                  = "tcp"
  from_port                    = 9100
  to_port                      = 9100
  description                  = "Prometheus scrapes node_exporter"
}

# ---------- Outbound: allow everything (package installs, image pulls) ----------
resource "aws_vpc_security_group_egress_rule" "jenkins_all" {
  security_group_id = aws_security_group.jenkins.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_egress_rule" "k8s_all" {
  security_group_id = aws_security_group.k8s.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_egress_rule" "db_all" {
  security_group_id = aws_security_group.db.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
