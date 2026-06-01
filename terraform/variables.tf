variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-1"
}

variable "alexa_skill_ids" {
  description = "Alexa Skill IDs allowed to invoke this Lambda (one per Amazon account)"
  type        = list(string)
  default     = []
}

variable "classcharts_email" {
  description = "ClassCharts parent account email"
  type        = string
  sensitive   = true
}

variable "classcharts_password" {
  description = "ClassCharts parent account password"
  type        = string
  sensitive   = true
}

variable "google_client_id" {
  description = "Google OAuth2 client ID"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_client_secret" {
  description = "Google OAuth2 client secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_refresh_token" {
  description = "Google OAuth2 refresh token (from scripts/get_google_token.py)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
}

variable "pupil_names" {
  description = "Comma-separated list of pupil first names to match in ClassCharts (e.g. 'Alice,Bob')"
  type        = string
  default     = ""
}

variable "prewarm_schedule" {
  description = "EventBridge cron schedule for cache pre-warm (UTC). BST=6:15, GMT=7:15."
  type        = string
  default     = "cron(15 6 ? * MON-FRI *)"
}

variable "family_context" {
  description = "Free-text context about the family injected into the briefing prompt (children's names, calendar email mappings, etc.). Kept in tfvars — never commit."
  type        = string
  sensitive   = true
}
