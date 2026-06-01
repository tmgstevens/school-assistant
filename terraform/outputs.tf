output "lambda_arn" {
  description = "Lambda ARN — paste this as the endpoint in the Alexa Developer Console"
  value       = aws_lambda_function.school_assistant.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.school_assistant.function_name
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.cache.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.school_assistant.repository_url
}
