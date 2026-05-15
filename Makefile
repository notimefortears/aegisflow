.PHONY: dev prod down logs db-migrate db-rollback test lint format build \
        shell-backend flower push-github

DC      := docker compose
DC_DEV  := $(DC) -f docker-compose.yml -f docker-compose.dev.yml
DC_PROD := $(DC) -f docker-compose.yml

# ── Environment ───────────────────────────────────────────────────────────────

## dev: Start the full development environment (hot-reload backend + Vite frontend)
dev:
	$(DC_DEV) up --build

## prod: Start the production stack (all services, nginx on 80/443)
prod:
	$(DC_PROD) up -d --build

## down: Stop and remove all containers (preserves volumes)
down:
	$(DC_PROD) down

## build: Rebuild all Docker images without starting services
build:
	$(DC_PROD) build

## logs: Tail logs from all running services (Ctrl-C to stop)
logs:
	$(DC_PROD) logs -f

# ── Database ──────────────────────────────────────────────────────────────────

## db-migrate: Apply all pending Alembic migrations
db-migrate:
	$(DC_PROD) exec backend alembic upgrade head

## db-rollback: Roll back the most recent Alembic migration
db-rollback:
	$(DC_PROD) exec backend alembic downgrade -1

# ── Quality assurance ────────────────────────────────────────────────────────

## test: Run the full pytest suite with coverage report
test:
	$(DC_PROD) exec backend pytest tests/ --cov=app --cov-report=term-missing --cov-report=html -v

## lint: Run ruff (linter) and mypy (type checks)
lint:
	$(DC_PROD) exec backend ruff check app/ tests/
	$(DC_PROD) exec backend mypy app/

## format: Auto-format source with black and isort
format:
	$(DC_PROD) exec backend black app/ tests/
	$(DC_PROD) exec backend isort app/ tests/

# ── Utilities ─────────────────────────────────────────────────────────────────

## shell-backend: Open an interactive bash shell inside the running backend container
shell-backend:
	$(DC_PROD) exec backend bash

## flower: Open the Celery Flower monitoring UI in the default browser
flower:
	@echo "Opening Flower UI at http://localhost:5555 ..."
	@open http://localhost:5555 2>/dev/null || xdg-open http://localhost:5555 2>/dev/null || \
		echo "Navigate to http://localhost:5555 in your browser"

# ── Git ───────────────────────────────────────────────────────────────────────

## push-github: Stage all changes, commit with today's date, and push to origin main
push-github:
	git add -A
	git commit -m "chore: update $$(date +'%Y-%m-%d %H:%M')"
	git push origin main

# ── Help ──────────────────────────────────────────────────────────────────────

## help: Show this help message
help:
	@grep -E '^## [a-zA-Z_-]+:' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ": "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' | \
		sed 's/## //'

.DEFAULT_GOAL := help
