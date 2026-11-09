PYTHON ?= python3
DBT    ?= dbt

.PHONY: all install generate dbt export test headline clean

all: generate dbt export test headline

install:
	$(PYTHON) -m pip install -r requirements.txt

generate:
	$(PYTHON) generator/generate.py

dbt:
	cd dbt && $(DBT) build --profiles-dir .

export:
	$(PYTHON) scripts/export_tableau.py

test:
	$(PYTHON) -m pytest -q tests

headline:
	$(PYTHON) scripts/print_headline.py

clean:
	rm -rf data dbt/target dbt/logs dbt/attrition_lens.duckdb .pytest_cache
