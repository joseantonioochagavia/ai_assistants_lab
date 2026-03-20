# Meeting Assistant

This module is the starting point for a future AI assistant focused on meeting workflows.

## Intended Scope

Over time, this module may include features for:

- audio transcription
- meeting summarization
- action item extraction
- reusable prompts and application entry points

## Current Status

This module now includes a minimal transcription flow using the OpenAI API. It lightly preprocesses audio before transcription, supports direct transcription for shorter files, uses chunked transcription for longer files, and cleans the raw transcript into a readable version without summarizing it. The rest of the meeting workflow remains scaffold-only.

## Transcription

Audio transcription is handled through the OpenAI transcription API using the `gpt-4o-transcribe` model by default.
Raw transcription cleaning uses `gpt-4.1-mini`.

Supported formats:

- `.mp3`
- `.wav`
- `.m4a`

Before transcription, the audio is converted to a mono 16 kHz WAV to give the API a consistent input format.

Longer files are automatically split into 20-minute chunks before transcription.
Chunked transcription uses overlap between chunks and keeps debug outputs for inspection.

After transcription, the raw text is cleaned and normalized while preserving meaning.

## Required Environment Variables

- `OPENAI_API_KEY`
- `OPENAI_TRANSCRIPTION_MODEL` (optional, defaults to `gpt-4o-transcribe`)

## Local Requirement

Chunked transcription uses `pydub` for audio loading and splitting. For formats such as `.mp3` and `.m4a`, make sure `ffmpeg` is installed on your machine.

## Example Usage

```bash
python -m meeting_assistant.app path/to/audio.mp3
```

The command saves the raw transcription to `meeting_assistant/outputs/transcripts/raw/<audio-file-name>.md`, the cleaned transcription to `meeting_assistant/outputs/transcripts/clean/<audio-file-name>.md`, chunk-level debug outputs to `meeting_assistant/outputs/transcripts/debug/`, and prints a short success message with the cleaned output path.
