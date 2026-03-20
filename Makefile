.PHONY: install transcriber_test

install:
	./scripts/setup.sh

transcriber_test:
	python -m unittest meeting_assistant.tests.test_transcriber
