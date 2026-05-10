.PHONY: help test lint format clean docker-build docker-run terraform-init terraform-plan terraform-apply infra-up infra-down infra-plan-local infra-init-local

help:
	@echo "Available commands:"
	@echo "  test           - Run tests"
	@echo "  lint           - Run linters"
	@echo "  format         - Format code"
	@echo "  clean          - Clean up generated files"
	@echo "  docker-build   - Build Docker image"
	@echo "  docker-run     - Run Docker container"
	@echo "  tf-init        - Initialize Terraform"
	@echo "  tf-plan        - Plan Terraform changes"
	@echo "  tf-apply       - Apply Terraform changes"
	@echo "  infra-up       - Start LocalStack"
	@echo "  infra-down     - Stop LocalStack"
	@echo "  infra-init-local - Init Terraform for LocalStack"
	@echo "  infra-plan-local - Plan Terraform against LocalStack"

test:
	pytest tests/ -v --cov=. --cov-report=term-missing

lint:
	flake8 . --exclude=.venv,venv,__pycache__,.pytest_cache
	mypy .

format:
	black .
	isort .

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -f .coverage

docker-build:
	docker build -t mvp-launch-backend .

docker-run:
	docker run -p 8000:8000 --env-file .env mvp-launch-backend

tf-init:
	cd infrastructure/terraform && terraform init

tf-plan:
	cd infrastructure/terraform && terraform plan -out=tfplan

tf-apply:
	cd infrastructure/terraform && terraform apply tfplan

tf-destroy:
	cd infrastructure/terraform && terraform destroy

# LocalStack targets for zero-cost infrastructure validation
infra-up:
	docker compose -f infrastructure/docker-compose.yml up -d

infra-down:
	docker compose -f infrastructure/docker-compose.yml down

infra-init-local: infra-up
	AWS_ACCESS_KEY_ID=test \
	AWS_SECRET_ACCESS_KEY=test \
	AWS_DEFAULT_REGION=us-east-1 \
	AWS_ENDPOINT_URL=http://localhost:4566 \
	AWS_SKIP_CREDENTIALS_VALIDATION=true \
	AWS_SKIP_METADATA_API_CHECK=true \
	AWS_SKIP_REQUESTING_ACCOUNT_ID=true \
	TF_VAR_environment=local \
	TF_VAR_db_password=test12345678 \
	TF_VAR_datadog_api_key="" \
	TF_VAR_availability_zones='["us-east-1a","us-east-1b"]' \
	cd infrastructure/terraform && terraform init -reconfigure

infra-plan-local: infra-up
	AWS_ACCESS_KEY_ID=test \
	AWS_SECRET_ACCESS_KEY=test \
	AWS_DEFAULT_REGION=us-east-1 \
	AWS_ENDPOINT_URL=http://localhost:4566 \
	AWS_SKIP_CREDENTIALS_VALIDATION=true \
	AWS_SKIP_METADATA_API_CHECK=true \
	AWS_SKIP_REQUESTING_ACCOUNT_ID=true \
	TF_VAR_environment=local \
	TF_VAR_db_password=test12345678 \
	TF_VAR_datadog_api_key="" \
	TF_VAR_availability_zones='["us-east-1a","us-east-1b"]' \
	cd infrastructure/terraform && terraform init -reconfigure && terraform plan
