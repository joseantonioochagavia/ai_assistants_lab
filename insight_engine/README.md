# Insight Engine

`insight_engine` is the repository module focused on turning cleaned meeting transcripts into structured business insight.
It sits downstream from transcription and focuses on understanding what people are struggling with, which patterns appear across conversations, and which product or AI agent opportunities are worth exploring.

## Overview

The `insight_engine` module is designed to:

- consume cleaned transcripts produced by `meeting_assistant`
- extract pains, friction points, and unmet needs from each meeting
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

The current CLI reads cleaned transcript markdown files and prints a structured JSON list to stdout.

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
    ]
  }
]
```

This command requires `OPENAI_API_KEY` to be set. You can optionally configure `OPENAI_DATA_EXTRACTION_MODE`; otherwise the module uses `gpt-4.1-mini`.
