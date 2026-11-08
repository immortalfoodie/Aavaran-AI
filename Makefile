.PHONY: dev test lint typecheck seed setup validate

dev:
	uvicorn api.routes:app --reload

test:
	pytest

validate:
	python tests/golden/run_golden_harness.py
	pytest tests/property tests/adversarial tests/golden -v

lint:
	ruff check .

typecheck:
	mypy engine api ml

seed:
	python -m scripts.seed

setup:
	pip install -e ".[dev]"
