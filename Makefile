test: test_unit test_integration

test_unit:
	PYTHONPATH=. pytest tests/unit

test_integration:
	PYTHONPATH=. pytest tests/integration
