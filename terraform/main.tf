terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── ECR repository ────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "school_assistant" {
  name                 = "school-assistant"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = false
  }

  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_ecr_lifecycle_policy" "school_assistant" {
  repository = aws_ecr_repository.school_assistant.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 3 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 3
      }
      action = { type = "expire" }
    }]
  })
}

# ── DynamoDB cache ────────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "cache" {
  name         = "school-assistant-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "date"

  attribute {
    name = "date"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

# ── IAM ───────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "lambda" {
  name = "school-assistant-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "school-assistant-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem"]
        Resource = aws_dynamodb_table.cache.arn
      },
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.classcharts.arn,
          aws_secretsmanager_secret.google_calendar.arn,
          aws_secretsmanager_secret.anthropic.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = aws_ssm_parameter.briefing_prompt.arn
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage", "ecr:BatchCheckLayerAvailability"]
        Resource = aws_ecr_repository.school_assistant.arn
      },
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
    ]
  })
}

# ── Lambda ────────────────────────────────────────────────────────────────────

resource "aws_lambda_function" "school_assistant" {
  function_name = "school-assistant"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.school_assistant.repository_url}:latest"
  architectures = ["arm64"]
  timeout       = 60

  environment {
    variables = {
      CACHE_TABLE_NAME            = aws_dynamodb_table.cache.name
      CLASSCHARTS_SECRET_NAME     = aws_secretsmanager_secret.classcharts.name
      GOOGLE_CALENDAR_SECRET_NAME = aws_secretsmanager_secret.google_calendar.name
      ANTHROPIC_SECRET_NAME       = aws_secretsmanager_secret.anthropic.name
      PUPIL_NAMES                 = var.pupil_names
      PROMPT_PARAMETER_NAME       = aws_ssm_parameter.briefing_prompt.name
    }
  }

  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_cloudwatch_event_rule" "prewarm" {
  name                = "school-assistant-prewarm"
  description         = "Pre-warm Lambda cache before 7:30am Alexa routine"
  schedule_expression = var.prewarm_schedule
}

resource "aws_cloudwatch_event_target" "prewarm" {
  rule      = aws_cloudwatch_event_rule.prewarm.name
  target_id = "school-assistant-lambda"
  arn       = aws_lambda_function.school_assistant.arn
}

resource "aws_lambda_permission" "prewarm" {
  statement_id  = "AllowEventBridgeInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.school_assistant.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.prewarm.arn
}

resource "aws_lambda_permission" "alexa" {
  for_each = toset(var.alexa_skill_ids)

  statement_id       = "AllowAlexaInvocation-${replace(each.value, ".", "-")}"
  action             = "lambda:InvokeFunction"
  function_name      = aws_lambda_function.school_assistant.function_name
  principal          = "alexa-appkit.amazon.com"
  event_source_token = each.value
}
