PYTHON ?= python

AUDIO_FILES ?=
INPUT_PATH ?=
WORKERS ?=
WORKSHEET_NAME ?= Sheet1
SPREADSHEET_ID ?=
SERVICE_ACCOUNT_JSON_PATH ?=
DEBUG_MODE ?=

.PHONY: install extract transcribe insight full-pipeline test test-transcriber test-insight test-refinement test-full-pipeline run_tests transcriber_test

install:
	./scripts/setup.sh

extract:
	@set -e; \
	input_path='$(INPUT_PATH)'; \
	if [ -n "$$input_path" ]; then \
		$(PYTHON) -m insight_engine.data_extraction "$$input_path"; \
	else \
		$(PYTHON) -m insight_engine.data_extraction; \
	fi

transcribe:
	@set -e; \
	audio_files='$(AUDIO_FILES)'; \
	if [ -z "$$audio_files" ]; then \
		echo "AUDIO_FILES is required, for example: make transcribe AUDIO_FILES=\"file1.m4a|file2.mp3\"" >&2; \
		exit 1; \
	fi; \
	IFS='|'; \
	set --; \
	for audio in $$audio_files; do \
		if [ -n "$$audio" ]; then \
			set -- "$$@" "$$audio"; \
		fi; \
	done; \
	$(PYTHON) -m meeting_assistant.app "$$@" $(if $(strip $(DEBUG_MODE)),--debug) $(if $(strip $(WORKERS)),--workers $(WORKERS))

insight:
	@set -e; \
	input_path='$(INPUT_PATH)'; \
	if [ -n "$$input_path" ]; then \
		set -- "$$input_path"; \
	else \
		set --; \
	fi; \
	$(PYTHON) -m insight_engine.insight_engine "$$@" $(if $(strip $(EXPORT_GOOGLE_SHEET)),--export-google-sheet) $(if $(strip $(WORKSHEET_NAME)),--worksheet-name $(WORKSHEET_NAME)) $(if $(strip $(SPREADSHEET_ID)),--spreadsheet-id $(SPREADSHEET_ID)) $(if $(strip $(SERVICE_ACCOUNT_JSON_PATH)),--service-account-json-path $(SERVICE_ACCOUNT_JSON_PATH))

full-pipeline:
	@set -e; \
	audio_files='$(AUDIO_FILES)'; \
	if [ -z "$$audio_files" ]; then \
		echo "AUDIO_FILES is required, for example: make full-pipeline AUDIO_FILES=\"file1.m4a|file2.mp3\"" >&2; \
		exit 1; \
	fi; \
	IFS='|'; \
	set --; \
	for audio in $$audio_files; do \
		if [ -n "$$audio" ]; then \
			set -- "$$@" "$$audio"; \
		fi; \
	done; \
	$(PYTHON) -m insight_engine.full_pipeline "$$@" $(if $(strip $(DEBUG_MODE)),--debug) $(if $(strip $(WORKERS)),--workers $(WORKERS)) $(if $(strip $(WORKSHEET_NAME)),--worksheet-name $(WORKSHEET_NAME)) $(if $(strip $(SPREADSHEET_ID)),--spreadsheet-id $(SPREADSHEET_ID)) $(if $(strip $(SERVICE_ACCOUNT_JSON_PATH)),--service-account-json-path $(SERVICE_ACCOUNT_JSON_PATH))

test:
	$(PYTHON) -m unittest

test-transcriber:
	$(PYTHON) -m unittest meeting_assistant.tests.test_transcriber

test-insight:
	$(PYTHON) -m unittest insight_engine.tests.test_insight_engine insight_engine.tests.test_data_extraction insight_engine.tests.test_refinement_engine insight_engine.tests.test_full_pipeline

test-refinement:
	$(PYTHON) -m unittest insight_engine.tests.test_refinement_engine insight_engine.tests.test_full_pipeline

test-full-pipeline:
	$(PYTHON) -m unittest insight_engine.tests.test_full_pipeline

run_tests: test

transcriber_test: test-transcriber
