# Meeting Assistant

This module is the starting point for a future AI assistant focused on meeting workflows.

## Intended Scope

Over time, this module may include features for:

- audio transcription
- meeting summarization
- action item extraction
- reusable prompts and application entry points

## Current Status

This module now includes a minimal transcription flow using the OpenAI API. It supports direct transcription for shorter files and chunked transcription for longer files. The rest of the meeting workflow remains scaffold-only.

## Transcription

Audio transcription is handled through the OpenAI transcription API using the `gpt-4o-transcribe` model by default.

Supported formats:

- `.mp3`
- `.wav`
- `.m4a`

Longer files are automatically split into 20-minute chunks before transcription.

## Required Environment Variables

- `OPENAI_API_KEY`
- `OPENAI_TRANSCRIPTION_MODEL` (optional, defaults to `gpt-4o-transcribe`)

## Local Requirement

Chunked transcription uses `pydub` for audio loading and splitting. For formats such as `.mp3` and `.m4a`, make sure `ffmpeg` is installed on your machine.

## Example Usage

```bash
python -m meeting_assistant.transcriber path/to/audio.mp3
```

The command saves the transcription to `outputs/transcripts/<audio-file-name>.md` and prints a short success message with the saved path.
