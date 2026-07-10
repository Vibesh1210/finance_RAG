.PHONY: up down sync migrate seed test gate gates verify-live

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

gate:
	uv run python gates/phase_$(PHASE_PADDED).py

gates:
	uv run python gates/run_all.py

verify-live:
	uv run python scripts/verify_live.py
