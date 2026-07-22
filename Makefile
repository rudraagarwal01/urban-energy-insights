DC = docker compose

.PHONY: up down logs migrate test-api

up:
	$(DC) up --build

down:
	$(DC) down -v

logs:
	$(DC) logs -f --tail=200

migrate:
	$(DC) run --rm api alembic upgrade head

test-api:
	docker run --rm -v $(PWD)/services/api:/app -w /app python:3.11-slim sh -c "pip install -q -r requirements.txt && pytest -q"
