.PHONY: up down sync migrate seed test test-unit test-integration lint check gate gates verify-live

PHASE ?= 0
PHASE_PADDED = $(shell printf '%02d' $(PHASE))

up:
	docker compose up -d --wait

down:
	docker compose down

sync:
	uv sync

migrate:
	uv run python -m us_rag.store.migrate

seed:
	uv run python -m us_rag.store.seed

test:
	uv run pytest -q

test-unit:
	uv run pytest -q -m "not integration"

test-integration:
	uv run pytest -q -m integration

lint:
	uv run ruff check backend/src backend/gates backend/scripts backend/tests

check: lint test-unit

gate:
	uv run python backend/gates/phase_$(PHASE_PADDED).py

gates:
	uv run python backend/gates/run_all.py

verify-live:
	uv run python backend/scripts/verify_live.py
