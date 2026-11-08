output "jenkins_public_ip" {
  value = aws_instance.jenkins.public_ip
}

output "master_public_ip" {
  value = aws_instance.master.public_ip
}

output "worker_public_ip" {
  value = aws_instance.worker.public_ip
}

output "db_private_ip" {
  value = aws_instance.db.private_ip
}

output "app_url" {
  description = "Open this once the application is deployed"
  value       = "http://${aws_instance.worker.public_ip}:30080"
}

output "jenkins_url" {
  value = "http://${aws_instance.jenkins.public_ip}:8080"
}

output "ssh_commands" {
  value = {
    jenkins = "ssh -i ~/.ssh/campusdesk ubuntu@${aws_instance.jenkins.public_ip}"
    master  = "ssh -i ~/.ssh/campusdesk ubuntu@${aws_instance.master.public_ip}"
    worker  = "ssh -i ~/.ssh/campusdesk ubuntu@${aws_instance.worker.public_ip}"
    db      = "ssh -i ~/.ssh/campusdesk -J ubuntu@${aws_instance.jenkins.public_ip} ubuntu@${aws_instance.db.private_ip}"
  }
}

# Ansible inventory, rewritten on every apply so the public IPs are always current.
resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../ansible/inventory/hosts.ini"
  file_permission = "0644"
  content = templatefile("${path.module}/inventory.tftpl", {
    jenkins_ip = aws_instance.jenkins.public_ip
    master_ip  = aws_instance.master.public_ip
    worker_ip  = aws_instance.worker.public_ip
    db_ip      = aws_instance.db.private_ip
  })
}
