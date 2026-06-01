.PHONY: venv install build deploy test clean

VENV    := .venv
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
PYTEST  := $(VENV)/bin/pytest

AWS_REGION     := eu-west-1
AWS_ACCOUNT_ID := $(shell aws sts get-caller-identity --query Account --output text 2>/dev/null)
ECR_REPO       := $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/school-assistant

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

build:
	aws ecr get-login-password --region $(AWS_REGION) | \
	  docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	docker build --platform linux/arm64 -t school-assistant .
	docker tag school-assistant:latest $(ECR_REPO):latest
	docker push $(ECR_REPO):latest
	aws lambda update-function-code \
	  --function-name school-assistant \
	  --image-uri $(ECR_REPO):latest \
	  --region $(AWS_REGION) > /dev/null

deploy:
	cd terraform && terraform apply -target=aws_ecr_repository.school_assistant -auto-approve
	$(MAKE) build
	cd terraform && terraform apply -auto-approve

test:
	PYTHONPATH=src $(PYTEST) tests/ -v

clean:
	rm -rf build lambda.zip __pycache__ .pytest_cache
	find . -name "*.pyc" -delete
