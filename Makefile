.PHONY: help test lint format clean docker-build docker-run terraform-init terraform-plan terraform-apply

help:
	@echo "Available commands:"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linters"
	@echo "  format       - Format code"
	@echo "  clean        - Clean up generated files"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo "  tf-init      - Initialize Terraform"
	@echo "  tf-plan      - Plan Terraform changes"
	@echo "  tf-apply     - Apply Terraform changes"

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
