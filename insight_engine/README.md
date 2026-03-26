# Insight Engine

`insight_engine` is the repository module focused on turning cleaned meeting transcripts into structured business insight.
It sits downstream from transcription and focuses on understanding what people are struggling with, which patterns appear across conversations, and which product or AI agent opportunities are worth exploring.

## Overview

The `insight_engine` module is designed to:

- consume cleaned transcripts produced by `meeting_assistant`
- extract pains, friction points, and unmet needs from each meeting
- extract relevant business themes discussed in each meeting
- identify recurring patterns across multiple conversations
- generate product ideas or AI agent concepts grounded in those patterns

In practice, this module converts qualitative conversation data into a more structured layer that can support analysis, prioritization, and opportunity discovery.

## Purpose

The purpose of `insight_engine` is to make interview and meeting data more useful for decision-making.
Its core focus is:

- identifying recurring pains that appear across conversations
- structuring qualitative data so it can be compared and reviewed systematically
- supporting business opportunity discovery with insight derived from real user language

Rather than stopping at transcription, this module is responsible for interpreting the content of conversations and surfacing signals that can inform product strategy, internal tooling, or new AI assistant ideas.

## Relationship With `meeting_assistant`

The two modules cover different parts of the workflow:

- `meeting_assistant` handles audio -> text
- `insight_engine` handles text -> business value

## CLI Usage

Stage 1 reads cleaned transcript markdown files and prints a structured JSON list to stdout.

Run it with the default cleaned transcripts directory:

```bash
python -m insight_engine.data_extraction
```

Run it against a specific directory:

```bash
python -m insight_engine.data_extraction meeting_assistant/outputs/transcripts/clean
```

Example output:

```json
[
  {
    "reunion": "Samuel Hurtado",
    "dolores": [
      "Mucho trabajo manual",
      "Falta de trazabilidad"
    ],
    "temas_clave": [
      "Trazabilidad",
      "Procesos manuales"
    ]
  }
]
```

This command requires `OPENAI_API_KEY` to be set. You can optionally configure `OPENAI_DATA_EXTRACTION_MODEL`; otherwise the module uses `gpt-4.1-mini`.

Stage 2 builds the final insight table with semantic deduplication plus LLM enrichment:

```bash
python -m insight_engine.insight_engine
```

You can also point it to a JSON file produced by stage 1:

```bash
python -m insight_engine.insight_engine path/to/structured_data.json
```

To export the resulting dataframe to Google Sheets:

```bash
python -m insight_engine.insight_engine --export-google-sheet --worksheet-name Sheet1
```

Relevant environment variables:

- `OPENAI_API_KEY`
- `OPENAI_DATA_EXTRACTION_MODEL` for stage 1
- `OPENAI_MODEL_INSIGHT_ENGINE` for stage 2 enrichment
- `OPENAI_EMBEDDING_MODEL` for semantic deduplication
- `INSIGHT_CATEGORY_OPTIONS` for the allowed categories, either inline text, JSON, or a local file path
- `INSIGHT_SYSTEM_PROMPT` for the enrichment system prompt, either inline text or a local file path
- `INSIGHT_TASK_PROMPT` for the enrichment task prompt, either inline text or a local file path
- `INSIGHT_ENGINE_COMPANY_CONTEXT` to guide ideas and KPIs, either as inline text or a local file path
- `GOOGLE_SHEETS_SPREADSHEET_ID` for export
- `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` for export
