.PHONY: install transcriber_test run_tests

install:
	./scripts/setup.sh

transcriber_test:
	python -m unittest meeting_assistant.tests.test_transcriber

run_tests:
	python -m unittest
