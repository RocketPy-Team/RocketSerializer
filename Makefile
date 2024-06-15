lint: isort black

isort:
	isort .

black:
	black .

pylint:
	pylint rocketserializer/ --output="pylint_report.txt"

tests:
	pytest

# tests-unit:

# tests-acceptance:

# tests-integration:

