.PHONY: help test lint format run-api run-worker run-mockhub up down clean

help:
	@echo "Available commands:"
	@echo "  make test         Run all unit, integration, and e2e tests"
	@echo "  make lint         Run ruff linter check"
	@echo "  make format       Format code using ruff"
	@echo "  make run-api      Run FastAPI dev server"
	@echo "  make run-worker   Run background job worker"
	@echo "  make run-mockhub  Run Chaos Mock Hub"
	@echo "  make up           Start all Docker Compose services"
	@echo "  make down         Stop all Docker Compose services"

test:
	pytest -v

lint:
	ruff check .

format:
	ruff format .

run-api:
	uvicorn app.api.main:app --reload --port 8000

run-worker:
	python -m app.queue.worker

run-mockhub:
	uvicorn mockhub.app:app --reload --port 8010

up:
	docker compose up --build -d

down:
	docker compose down -v

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
