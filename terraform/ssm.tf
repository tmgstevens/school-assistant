resource "aws_ssm_parameter" "briefing_prompt" {
  name  = "/school-assistant/briefing-prompt"
  type  = "String"
  value = templatefile("${path.module}/prompt.txt", {
    family_context = var.family_context
  })
}
