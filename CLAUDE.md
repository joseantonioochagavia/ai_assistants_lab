# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

Uses Python 3.10.13 via pyenv with the `ai-assistants` virtual environment.

```bash
make install        # runs scripts/setup.sh: sets up pyenv venv and installs requirements
```

Copy `.env.example` to `.env` and fill in at minimum `OPENAI_API_KEY`. See README.md for the full list of optional env vars.

`ffmpeg` must be installed locally for chunked transcription of `.mp3` and `.m4a` files.

## Common Commands

```bash
# Transcription
make transcribe AUDIO_FILES="file.m4a"
make transcribe AUDIO_FILES="file1.m4a|file2.m4a" WORKERS=2 DEBUG_MODE=1

# Insight pipeline
make extract                                         # stage 1: transcripts → structured JSON
make insight                                         # stage 2: JSON → enriched/refined dataframe
make insight INPUT_PATH=path/to/structured_data.json
make insight EXPORT_GOOGLE_SHEET=1 WORKSHEET_NAME=Sheet1

# Full pipeline (audio → Google Sheets in one command)
make full-pipeline AUDIO_FILES="file1.m4a|file2.m4a" WORKSHEET_NAME=Sheet1 WORKERS=2

# Tests
make test                         # all tests
make test-transcriber             # meeting_assistant tests only
make test-insight                 # all insight_engine tests
make test-refinement              # refinement + full-pipeline tests only
make test-full-pipeline           # full-pipeline tests only
```

Individual test class/method:
```bash
python -m unittest meeting_assistant.tests.test_transcriber.TestClassName.test_method_name
```

## Architecture

### Data Flow

```
audio files
    → meeting_assistant (transcribe + clean)
    → meeting_assistant/outputs/transcripts/clean/*.md
    → insight_engine.data_extraction (extract pains/themes per meeting → JSON)
    → insight_engine.insight_engine (deduplicate → enrich → refine → DataFrame)
    → insight_engine.export_data_to_google_sheet (optional Google Sheets export)
```

### Module Boundaries

- **`common/`** — shared config (`get_env`) and OpenAI client factory (`create_openai_client`). All modules import from here; no assistant-specific logic lives here.

- **`meeting_assistant/`** — audio → text pipeline:
  - `preprocess.py`: converts audio to mono 16kHz WAV via pydub/ffmpeg
  - `transcribe.py`: calls OpenAI transcription API, handles chunking for long files (splits into 10-min chunks)
  - `clean.py`: cleans raw transcript with `gpt-4.1-mini` without summarizing
  - `save.py`: writes raw/clean/debug output to `meeting_assistant/outputs/transcripts/`
  - `app.py`: CLI entry point, wires the pipeline, supports `--workers` (concurrent transcription) and `--debug`

- **`insight_engine/`** — text → structured business insight pipeline:
  - `data_extraction.py`: reads cleaned transcript `.md` files, calls LLM to extract per-meeting pain points and themes, outputs a JSON list
  - `insight_engine.py`: deduplicates pain points (exact then semantic via embeddings), enriches clusters into structured rows (Categoria/Dolores/ideas/kpi_medicion/Fuentes/Tiempo_estimado), calls `refinement_engine` iteratively, returns the best-scoring DataFrame
  - `refinement_engine.py`: verifier/refiner loop — scores the table, identifies merge candidates, applies high-confidence merges, runs up to 3 iterations and returns the best version
  - `export_data_to_google_sheet.py`: writes the final DataFrame to a Google Sheets worksheet
  - `full_pipeline.py`: orchestrates everything end-to-end from audio files to Google Sheets

### Key Insight Engine Concepts

- **Semantic deduplication**: uses OpenAI embeddings + cosine similarity (threshold 0.88) to cluster pain points before enrichment
- **Enrichment**: LLM is called in batches to produce structured rows from pain clusters; uses structured output (`json_schema`) for reliability
- **Refinement loop**: verifier scores the table and returns `merge_candidates`; refiner applies merges conservatively to avoid information loss; best-scoring iteration is returned (stored in `dataframe.attrs["refinement_metadata"]`)
- **Prompt/category configuration**: `INSIGHT_CATEGORY_OPTIONS`, `INSIGHT_SYSTEM_PROMPT`, `INSIGHT_TASK_PROMPT`, and `REFINEMENT_SYSTEM_PROMPT` env vars accept either inline text, JSON (for categories), or a local file path — resolved at runtime via `_read_text_or_file`

### Local-only Directories (not in git)

- `meeting_assistant/audios/` — place source audio files here; bare filenames work in make commands
- `meeting_assistant/outputs/` — all generated transcripts and debug artifacts
- `insight_engine/docs/private/` — prompt files, sample CSVs, company context, and structured data snapshots
