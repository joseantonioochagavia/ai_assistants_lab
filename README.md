# ai_assistants_lab

A public Python repository for small, modular AI assistants focused on workflow automation.

## Current Status

The repository now includes a working first transcription flow for the `meeting_assistant` module using the OpenAI API. Audio is lightly preprocessed before transcription, longer recordings are split into chunks, raw transcripts are cleaned into readable text, and both versions are saved as markdown.

## Repository Structure

- `common/`: shared configuration helpers and OpenAI client creation
- `meeting_assistant/`: the first assistant module, currently focused on transcription
- `docs/prompts/`: prompt files used to drive repository iterations
- `scripts/`: setup helpers for local development

## Setup

Install the project dependencies with:

```bash
make install
```

Or directly with:

```bash
pip install -r requirements.txt
```

Create a local `.env` file based on `.env.example` and set:

- `OPENAI_API_KEY`
- `OPENAI_TRANSCRIPTION_MODEL` (optional, defaults to `gpt-4o-transcribe`)
- `OPENAI_DATA_EXTRACTION_MODEL` (optional, defaults to `gpt-4.1-mini`)
- `OPENAI_MODEL_INSIGHT_ENGINE` (optional, defaults to `gpt-5.4-mini`)
- `OPENAI_EMBEDDING_MODEL` (optional, defaults to `text-embedding-3-small`)
- `INSIGHT_CATEGORY_OPTIONS` (optional, accepts inline text, JSON, or a local text-file path)
- `INSIGHT_SYSTEM_PROMPT` (optional, accepts inline text or a local text-file path)
- `INSIGHT_TASK_PROMPT` (optional, accepts inline text or a local text-file path)
- `INSIGHT_ENGINE_COMPANY_CONTEXT` (optional, accepts inline text or a local text-file path such as `insight_engine/docs/private/company_context.txt`)
- `GOOGLE_SHEETS_SPREADSHEET_ID` (required only for Google Sheets export)
- `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` (required only for Google Sheets export)

For chunked transcription of formats such as `.mp3` and `.m4a`, make sure `ffmpeg` is installed locally.

## Meeting Assistant

The `meeting_assistant` module currently supports audio transcription through the OpenAI transcription API.

Current behavior:

- supports `.mp3`, `.wav`, and `.m4a`
- preprocesses audio into a mono 16 kHz WAV before transcription
- uses direct transcription for shorter audio files
- automatically splits longer audio into 20-minute chunks
- cleans the raw transcript with `gpt-4.1-mini` without summarizing it
- saves raw transcripts to `meeting_assistant/outputs/transcripts/raw/<audio-file-name>.md`
- saves cleaned transcripts to `meeting_assistant/outputs/transcripts/clean/<audio-file-name>.md`
- saves chunk-level and merged debug transcripts to `meeting_assistant/outputs/transcripts/debug/`

Example:

```bash
python -m meeting_assistant.app path/to/audio.m4a
```

## Insight Engine

The `insight_engine` module supports two stages:

- `insight_engine.data_extraction`: reads cleaned transcripts and extracts meeting-level pain points plus themes
- `insight_engine.insight_engine`: deduplicates pain points semantically, enriches them into actionable solutions, and returns the final insight table as a pandas DataFrame

Example:

```bash
python -m insight_engine.data_extraction
```

You can also point it to a specific transcript directory:

```bash
python -m insight_engine.data_extraction meeting_assistant/outputs/transcripts/clean
```

To build the final insight table directly from cleaned transcripts:

```bash
python -m insight_engine.insight_engine
```

You can also point the final stage to a JSON file produced by `insight_engine.data_extraction`:

```bash
python -m insight_engine.insight_engine path/to/structured_data.json
```

To export the resulting table to Google Sheets:

```bash
python -m insight_engine.insight_engine --export-google-sheet --worksheet-name Sheet1
```

## Tests

The repository includes lightweight unit tests for the transcription and insight flows. Run them with:

```bash
python -m unittest
```

## Direction

This repository remains intentionally simple:

- modular assistant-specific directories
- minimal shared abstractions
- incremental feature growth driven by real workflows

## Repository Philosophy

- Modular: each assistant lives in its own directory with clear boundaries
- Simple: start with minimal scaffolding before adding real logic
- Extensible: shared utilities should support future assistants without forcing early abstractions
