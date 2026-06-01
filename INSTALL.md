# School Assistant — Install Guide

Alexa skill that gives a spoken morning briefing for kids before school. Pulls homework, timetable, and announcements from ClassCharts, combines with Google Calendar, and uses Claude to synthesise a 30-second briefing.

Invoked before 3pm it briefs for today; invoked after 3pm it briefs for tomorrow.

## Architecture

- **Lambda** (ARM64 container, eu-west-1) handles Alexa requests
- **DynamoDB** caches the briefing per date (2-hour TTL) so repeated invocations are fast
- **EventBridge** triggers a pre-warm at 7:15am weekdays so the cache is hot before the 7:30am routine
- **SSM Parameter Store** holds the briefing prompt — update without rebuilding the image
- **Secrets Manager** holds ClassCharts, Google OAuth, and Anthropic credentials

## Prerequisites

- AWS CLI configured (`aws sts get-caller-identity` should work)
- Terraform >= 1.0
- Docker (with `buildx` for ARM64 cross-compilation if not on ARM)
- Python 3.11+
- An Anthropic API key
- A ClassCharts parent account
- A Google Cloud project with Calendar API enabled and OAuth2 credentials (Desktop app type)
- An Alexa Developer account

## Local setup

```bash
cp .env.example .env
# Fill in .env with real values

make install          # create venv and install deps
make test             # run unit tests
python scripts/run_local.py   # full local dry-run against live APIs
```

### Getting a Google refresh token

```bash
python scripts/get_google_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

This prints a URL to open in your browser. After authorising, your browser will redirect to `http://localhost:8080` and show "This site can't be reached" — that's expected. Copy the full URL from the address bar and paste it back into the script. It will print the refresh token to add to `.env`.

> **Note:** Your Google Cloud OAuth app must be published (Production status) to get a non-expiring refresh token. Apps in Testing mode issue tokens that expire after 7 days.

## First deploy

Terraform needs the ECR repo to exist before the Lambda image can be pushed:

```bash
make deploy
```

This runs `terraform apply` (ECR only), builds and pushes the Docker image, then runs `terraform apply` for everything else.

After the first deploy, `terraform output lambda_arn` gives you the ARN you need for the Alexa skill endpoint.

## Setting up the Alexa skill

1. Go to [developer.amazon.com](https://developer.amazon.com) and create a new skill
   - Type: Custom
   - Hosting: Provision your own
2. Set the invocation name (e.g. "school briefing")
3. Under **Endpoint**, paste the Lambda ARN
4. Copy the Skill ID from the browser URL
5. Add it to `terraform/terraform.tfvars`:
   ```hcl
   alexa_skill_ids = ["amzn1.ask.skill.YOUR-SKILL-ID"]
   ```
6. Run `terraform apply` to grant the skill permission to invoke Lambda
7. Save the endpoint in the Alexa console — it should now succeed

If you have Echo devices on multiple Amazon accounts, create a skill on each account and add all IDs to `alexa_skill_ids`.

## Updating the prompt

The briefing prompt lives in SSM and can be updated without rebuilding the image. Edit the live prompt directly:

```bash
aws ssm put-parameter \
  --name /school-assistant/briefing-prompt \
  --value "$(cat terraform/prompt.txt)" \
  --type String \
  --overwrite
```

> **Note:** `prompt.txt` uses `${family_context}` (a Terraform variable) as well as `{briefing_date}`, `{current_datetime}`, and `{data}` (runtime placeholders filled by Lambda). If you're updating SSM directly rather than via Terraform, make sure `${family_context}` has been substituted with your actual family context before pushing.

After updating the prompt, clear the DynamoDB cache so the next invocation picks it up:

```bash
aws dynamodb delete-item \
  --table-name school-assistant-cache \
  --key '{"date": {"S": "YYYY-MM-DD"}}'
```

## Family context

The `family_context` Terraform variable is injected into the prompt at deploy time. It should contain anything family-specific that the LLM needs to know — children's names, calendar attendee email mappings, etc. Keep it in `terraform.tfvars` (gitignored). See `terraform/terraform.tfvars.example` for the expected format.

## Subsequent deploys

After changing Python source or the Dockerfile:

```bash
make build    # rebuilds and pushes image, updates Lambda
```

After changing Terraform only:

```bash
cd terraform && terraform apply
```

## DST adjustment

The EventBridge pre-warm schedule is in UTC. Update `prewarm_schedule` in `terraform/terraform.tfvars` when the clocks change:

- **BST (late March – late October):** `cron(15 6 ? * MON-FRI *)` (UTC+1)
- **GMT (late October – late March):** `cron(15 7 ? * MON-FRI *)` (UTC+0)

Then run `terraform apply`.

## Secrets

All secrets are in `terraform/terraform.tfvars` (gitignored) and `.env` (gitignored). Neither file should ever be committed. Terraform stores them in Secrets Manager at deploy time; the Lambda reads them at runtime.
