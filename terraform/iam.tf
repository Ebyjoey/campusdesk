# Lets the CloudWatch agent on the instances publish memory, disk and logs.
# The database host has no profile: it has no internet route unless NAT is on.

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cw" {
  name               = "campusdesk-ec2-cloudwatch"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "cw_agent" {
  role       = aws_iam_role.cw.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "cw" {
  name = "campusdesk-ec2-cloudwatch"
  role = aws_iam_role.cw.name
}
