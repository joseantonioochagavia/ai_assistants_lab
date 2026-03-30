# ai_assistants_lab

A public Python repository for small, modular AI assistants focused on workflow automation.

## Current Status

The repository includes a working transcription flow for `meeting_assistant` and a multi-stage `insight_engine` pipeline. Audio is lightly preprocessed before transcription, longer recordings are split into chunks, raw transcripts are cleaned into readable text, and the downstream insight flow extracts pains, builds an actionable table, and refines that table with an iterative verifier/refiner loop before export.

## Repository Structure

- `common/`: shared configuration helpers and OpenAI client creation
- `meeting_assistant/`: the first assistant module, currently focused on transcription
- `insight_engine/`: structured extraction, insight enrichment, iterative refinement, and Google Sheets export
- `docs/prompts/`: prompt files used to drive repository iterations
- `scripts/`: setup helpers for local development

## Local Folders

These folders are part of the working setup but are ignored by git or generated locally:

- `meeting_assistant/audios/`: place source audio files here if you want to organize local inputs
- `meeting_assistant/outputs/`: generated transcripts and debug artifacts are written here at runtime
- `meeting_assistant/outputs/transcripts/raw/`: raw transcript markdown output
- `meeting_assistant/outputs/transcripts/clean/`: cleaned transcript markdown output
- `meeting_assistant/outputs/transcripts/debug/`: chunk-level and merged debug output
- `insight_engine/docs/private/`: prompt files, sample CSVs, and local refinement/enrichment context
- `data/`: optional local data area for experiments or scratch inputs
- `notebooks/`: optional local analysis notebooks

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
- `REFINEMENT_SYSTEM_PROMPT` (optional, accepts inline text or a local text-file path for the verifier/refiner loop)
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
make transcribe AUDIO_FILES="path/to/audio.m4a"
```

## Insight Engine

The `insight_engine` module supports three main steps:

- `insight_engine.data_extraction`: reads cleaned transcripts and extracts meeting-level pain points plus themes
- `insight_engine.insight_engine`: deduplicates pain points semantically, enriches them into actionable solutions, runs iterative table refinement, and returns the best insight table as a pandas DataFrame
- `insight_engine.full_pipeline`: runs the full flow from selected audio files through Google Sheets export
- `insight_engine.refinement_engine`: internal helper module used by `insight_engine.insight_engine` for verifier/refiner scoring and table refinement

Example:

```bash
make insight
```

You can also point it to a specific transcript directory:

```bash
make extract INPUT_PATH=meeting_assistant/outputs/transcripts/clean
```

You can also point the final stage to a JSON file produced by `insight_engine.data_extraction`:

```bash
make insight INPUT_PATH=path/to/structured_data.json
```

To export the resulting table to Google Sheets:

```bash
make insight EXPORT_GOOGLE_SHEET=1 WORKSHEET_NAME=Sheet1
```

To run the full flow from one or more audio files directly into Google Sheets:

```bash
make full-pipeline AUDIO_FILES="audio1.m4a|audio2.m4a" WORKSHEET_NAME=Sheet1 WORKERS=2
```

This command transcribes only the audio files you pass in, extracts structured pains from only those cleaned transcripts, builds and refines the insight table, and then exports the final result to the configured spreadsheet.

## Tests

The repository includes lightweight unit tests for the transcription and insight flows. Run them with:

```bash
make test
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
