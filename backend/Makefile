# Backend Makefile for common development tasks

.PHONY: help install test test-auth test-quotes test-ai test-docs test-users test-cov lint format clean

help:  ## Show this help
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt

test:  ## Run all tests
	python scripts/run_tests.py all

test-auth:  ## Run authentication tests
	python scripts/run_tests.py auth

test-quotes:  ## Run quotes tests
	python scripts/run_tests.py quotes

test-ai:  ## Run AI tests
	python scripts/run_tests.py ai

test-docs:  ## Run documents tests
	python scripts/run_tests.py documents

test-users:  ## Run user management tests
	python scripts/run_tests.py users

test-cov:  ## Run tests with coverage report
	python scripts/run_tests.py coverage

test-parallel:  ## Run tests in parallel
	python scripts/run_tests.py all --parallel

lint:  ## Run linting
	flake8 src tests
	black --check src tests
	isort --check-only src tests

format:  ## Format code
	black src tests
	isort src tests

clean:  ## Clean up generated files
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

dev-setup:  ## Set up development environment
	pip install -r requirements.txt
	pre-commit install

docker-test:  ## Run tests in Docker
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# CI/CD commands
ci-test:  ## Run tests for CI
	python -m pytest tests/ --cov=src --cov-report=xml --cov-report=term-missing --junitxml=test-results.xml

security-scan:  ## Run security scan
	bandit -r src/
	safety check