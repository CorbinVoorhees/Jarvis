run:
	python -m uvicorn app.main:app --reload

test:
	pytest

lint:
	python -m ruff check .

format:
	python -m black .

check:
	pytest
	python -m ruff check .