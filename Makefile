PYTHON_PACKAGES = pythonfuzz/*.py tests/**/*.py

all: check test

check: check_ruff check_mypy check_black check_kacl

check_ruff: .devel_installed
	ruff check $(PYTHON_PACKAGES)

check_black: .devel_installed
	black --check --diff $(PYTHON_PACKAGES)

check_mypy: .devel_installed
	mypy $(PYTHON_PACKAGES)

check_kacl: .devel_installed
	kacl-cli verify

test: test_unit test_integration test_build

test_unit: .devel_installed
	PYTHONPATH=. pytest tests/unit

test_integration: .devel_installed
	PYTHONPATH=. pytest tests/integration

test_build: .devel_installed
	python3 -m build

install_devel: .devel_installed

.devel_installed:
	pip install -e .[devel]
	touch $@

format:
	ruff check --fix-only $(PYTHON_PACKAGES) | true
	black $(PYTHON_PACKAGES)

clean:
	rm -rf dist cobrafuzz.egg-info crashes .devel_installed

.PHONY: check check_black check_kacl check_mypy check_ruff test test_build test_integration test_unit install_devel
