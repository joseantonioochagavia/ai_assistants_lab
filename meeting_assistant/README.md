# Meeting Assistant

This module is the starting point for a future AI assistant focused on meeting workflows.

## Intended Scope

Over time, this module may include features for:

- audio transcription
- meeting summarization
- action item extraction
- reusable prompts and application entry points

## Current Status

This module now includes a minimal first transcription flow using the OpenAI API. The rest of the meeting workflow remains scaffold-only.

## Transcription

Audio transcription is handled through the OpenAI transcription API using the `gpt-4o-transcribe` model by default.

Supported formats:

- `.mp3`
- `.wav`
- `.m4a`

## Required Environment Variables

- `OPENAI_API_KEY`
- `OPENAI_TRANSCRIPTION_MODEL` (optional, defaults to `gpt-4o-transcribe`)

## Example Usage

```bash
python -m meeting_assistant.transcriber path/to/audio.mp3
```
