PYTHON_PACKAGES = cobrafuzz/*.py tests/**/*.py examples/**/*.py

all: check test

check: check_ruff check_mypy check_black check_kacl check_dead_code

check_ruff: .devel_installed
	ruff check $(PYTHON_PACKAGES)

check_black: .devel_installed
	black --check --diff $(PYTHON_PACKAGES)

check_mypy: .devel_installed
	mypy $(PYTHON_PACKAGES)

check_kacl: .devel_installed
	kacl-cli verify

check_dead_code: .devel_installed
	vulture --ignore-names "CobraFuzz" cobrafuzz

test: test_unit test_integration test_build

test_unit: .devel_installed
	PYTHONPATH=. timeout -k 30 60 pytest -vv --cov-report term:skip-covered --cov-report xml:coverage.xml --cov=cobrafuzz --cov=tests.unit --cov-branch --cov-fail-under=100 tests/unit

test_integration: .devel_installed
	PYTHONPATH=. timeout -k 30 60 pytest -vv tests/integration

test_build: .devel_installed
	python3 -m build

install_devel: .devel_installed

.devel_installed: pyproject.toml
	pip install -U pip
	pip install -e .[devel]
	touch $@

format:
	ruff check --fix-only $(PYTHON_PACKAGES) | true
	black $(PYTHON_PACKAGES)

fuzz-%:
	python examples/fuzz_$*/fuzz.py --crash-dir examples/fuzz_$*/crashes --state examples/fuzz_$*/state.json --close-stdout --close-stderr examples/fuzz_$*/seeds

regr-%:
	@python examples/fuzz_$*/fuzz.py --crash-dir examples/fuzz_$*/crashes --regression

clean-%:
	@rm -f examples/fuzz_$*/state.json
	@rm -f examples/fuzz_$*/crashes/*

clean:
	rm -rf dist cobrafuzz.egg-info crashes .devel_installed .ruff_cache build

.PHONY: check check_black check_kacl check_mypy check_ruff test test_build test_integration test_unit install_devel
