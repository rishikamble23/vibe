.PHONY: up down test seed demo reset build lint ci

# Default target
.DEFAULT_GOAL := help

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(GREEN)SHELFLINE - Deadline-Driven Dispatch for Perishable Aid$(NC)"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start all services with docker-compose
	@echo "$(GREEN)Starting SHELFLINE services...$(NC)"
	docker-compose -f docker-compose.yml up -d
	@echo "$(GREEN)Services started!$(NC)"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Frontend: http://localhost:5173"
	@echo "  API Docs: http://localhost:8000/docs"

down: ## Stop all services
	@echo "$(YELLOW)Stopping SHELFLINE services...$(NC)"
	docker-compose -f docker-compose.yml down

down-v: ## Stop all services and remove volumes
	@echo "$(RED)Stopping SHELFLINE services and removing volumes...$(NC)"
	docker-compose -f docker-compose.yml down -v

build: ## Build all Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	docker-compose -f docker-compose.yml build

logs: ## Show logs from all services
	docker-compose -f docker-compose.yml logs -f

logs-backend: ## Show backend logs
	docker-compose -f docker-compose.yml logs -f backend

logs-frontend: ## Show frontend logs
	docker-compose -f docker-compose.yml logs -f frontend

# Backend commands
backend-shell: ## Open shell in backend container
	docker-compose -f docker-compose.yml exec backend bash

backend-test: ## Run backend tests
	cd shelfline/backend && pytest -v --tb=short

backend-test-watch: ## Run backend tests in watch mode
	cd shelfline/backend && pytest-watch -- -v

backend-lint: ## Run backend linting
	cd shelfline/backend && ruff check .

backend-lint-fix: ## Run backend linting with auto-fix
	cd shelfline/backend && ruff check . --fix

backend-format: ## Format backend code
	cd shelfline/backend && ruff format .

backend-migrate: ## Run database migrations
	cd shelfline/backend && alembic upgrade head

backend-migrate-create: ## Create new migration (usage: make backend-migrate-create MSG="description")
	cd shelfline/backend && alembic revision --autogenerate -m "$(MSG)"

backend-migrate-check: ## Check for pending migrations
	cd shelfline/backend && alembic check

# Frontend commands
frontend-shell: ## Open shell in frontend container
	docker-compose -f docker-compose.yml exec frontend sh

frontend-test: ## Run frontend tests
	cd frontend && npm test

frontend-lint: ## Run frontend linting
	cd frontend && npm run lint

frontend-typecheck: ## Run TypeScript type checking
	cd frontend && npx tsc --noEmit

frontend-build: ## Build frontend for production
	cd frontend && npm run build

# Database commands
db-shell: ## Open psql shell
	docker-compose -f docker-compose.yml exec postgres psql -U shelfline -d shelfline

db-reset: ## Reset database (drop all tables and recreate)
	docker-compose -f docker-compose.yml exec postgres psql -U shelfline -d shelfline -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	$(MAKE) backend-migrate

# Seed data
seed: ## Seed database with demo data
	@echo "$(GREEN)Seeding database...$(NC)"
	cd backend && python -m app.sim.seed
	@echo "$(GREEN)Database seeded!$(NC)"

# Demo
demo: ## Run demo scenario (usage: make demo SCENARIO=S01)
	@echo "$(GREEN)Running demo scenario: $(SCENARIO)$(NC)"
	cd backend && python -m app.sim.scenarios.run $(SCENARIO)

# Reset everything
reset: down-v up seed ## Full reset: stop, remove volumes, start, seed
	@echo "$(GREEN)Full reset complete!$(NC)"

# CI simulation
ci: backend-lint backend-test frontend-lint frontend-typecheck frontend-build ## Run all CI checks locally
	@echo "$(GREEN)All CI checks passed!$(NC)"

# Development helpers
dev-backend: ## Run backend locally (outside Docker)
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run frontend locally (outside Docker)
	cd frontend && npm run dev

install-backend: ## Install backend dependencies
	cd backend && pip install -r requirements.txt

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

install: install-backend install-frontend ## Install all dependencies