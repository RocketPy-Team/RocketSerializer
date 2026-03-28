format:
	@ruff check --select I --fix
	@ruff format .
	@echo Ruff formatting completed.


ruff-lint:
	@echo Running ruff check...
	@ruff check
	@echo Ruff linter check completed.

pylint:
	@echo Running pylint check...
	@pylint examples/ rocketserializer/ tests/
	@echo Pylint check completed.

lint: ruff-lint pylint

tests:
	pytest

# tests-unit:

# tests-acceptance:

# tests-integration:

install:
	pip install -r requirements.in
	pip install -r requirements-dev.txt
	pip install -e .
