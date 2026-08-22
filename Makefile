.PHONY: install lint test smoke verify

install:
	python -m pip install -e . ruff

lint:
	ruff check .
	ruff format --check .

test:
	python -m unittest discover -s tests -v

smoke:
	reliability-lab run --source data/events.jsonl --db artifacts/lab.db
	reliability-lab report --db artifacts/lab.db --output artifacts/report.json

verify: lint test smoke
