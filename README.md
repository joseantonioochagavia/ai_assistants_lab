# ai_assistants_lab

A public Python repository for small, modular AI assistants focused on workflow automation.

## Current Status

The repository now includes a working first transcription flow for the `meeting_assistant` module using the OpenAI API. Longer audio files are handled by splitting them into chunks before transcription, and the final transcript is saved as markdown.

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

For chunked transcription of formats such as `.mp3` and `.m4a`, make sure `ffmpeg` is installed locally.

## Meeting Assistant

The `meeting_assistant` module currently supports audio transcription through the OpenAI transcription API.

Current behavior:

- supports `.mp3`, `.wav`, and `.m4a`
- uses direct transcription for shorter audio files
- automatically splits longer audio into 20-minute chunks
- saves the final result to `outputs/transcripts/<audio-file-name>.md`

Example:

```bash
python -m meeting_assistant.transcriber path/to/audio.m4a
```

## Tests

The repository includes lightweight unit tests for the transcription flow. Run them with:

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
