resource "aws_ssm_parameter" "briefing_prompt" {
  name  = "/school-assistant/briefing-prompt"
  type  = "String"
  value = templatefile("${path.module}/prompt.txt", {
    family_context = var.family_context
  })
}

resource "aws_ssm_parameter" "family_context" {
  name  = "/school-assistant/family-context"
  type  = "String"
  value = var.family_context
}
