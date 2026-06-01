resource "aws_secretsmanager_secret" "classcharts" {
  name        = "school-assistant/classcharts"
  description = "ClassCharts parent account credentials"
}

resource "aws_secretsmanager_secret_version" "classcharts" {
  secret_id = aws_secretsmanager_secret.classcharts.id
  secret_string = jsonencode({
    email    = var.classcharts_email
    password = var.classcharts_password
  })
}

resource "aws_secretsmanager_secret" "google_calendar" {
  name        = "school-assistant/google-calendar"
  description = "Google Calendar OAuth2 credentials"
}

resource "aws_secretsmanager_secret_version" "google_calendar" {
  secret_id = aws_secretsmanager_secret.google_calendar.id
  secret_string = jsonencode({
    client_id     = var.google_client_id
    client_secret = var.google_client_secret
    refresh_token = var.google_refresh_token
  })
}

resource "aws_secretsmanager_secret" "anthropic" {
  name        = "school-assistant/anthropic"
  description = "Anthropic API key"
}

resource "aws_secretsmanager_secret_version" "anthropic" {
  secret_id = aws_secretsmanager_secret.anthropic.id
  secret_string = jsonencode({
    api_key = var.anthropic_api_key
  })
}
