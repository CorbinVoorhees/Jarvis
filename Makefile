run:
	python -m uvicorn app.main:app --reload

test:
	pytest

lint:
	python -m ruff check .

format:
	python -m black .

migrate:
	python -m alembic upgrade head

check:
	pytest
	python -m ruff check .