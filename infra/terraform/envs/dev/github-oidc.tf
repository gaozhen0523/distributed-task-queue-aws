#infra/terraform/envs/dev/github-oidc.tf
# GitHub OIDC Provider
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]
}

# AssumeRole policy
data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:gaozhen0523/distributed-task-queue-aws:*"
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "distributed-task-queue-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
}

# 最小权限：ECR + ECS + S3 tfstate + DynamoDB lock + Logs
data "aws_iam_policy_document" "github_actions_policy" {
  # ECR push/pull
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:PutImage"
    ]
    resources = ["*"]
  }

  # ECS task definition + service update
  statement {
    effect = "Allow"
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DeregisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeServices",
      "ecs:UpdateService"
    ]
    resources = ["*"]
  }

  # 允许传递 task roles（dev 层创建的两个）
  statement {
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "arn:aws:iam::*:role/dist-*-task-role",
      "arn:aws:iam::*:role/dist-*-execution-role"
    ]
  }

  # CloudWatch logs（主要是 terraform 本身 / ECS 不太需要，但给一点无妨）
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:DescribeLogGroups",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }

  # S3 backend for terraform state (envs/dev + app)
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    resources = [
      "arn:aws:s3:::distributed-task-queue-tfstate",
      "arn:aws:s3:::distributed-task-queue-tfstate/*"
    ]
  }

  # DynamoDB lock table
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem"
    ]
    resources = [
      "arn:aws:dynamodb:us-east-1:*:table/distributed-task-queue-tfstate-lock"
    ]
  }
}

resource "aws_iam_role_policy" "github_actions_inline" {
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_policy.json
}
