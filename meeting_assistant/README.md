# Meeting Assistant

This module is the starting point for a future AI assistant focused on meeting workflows.

## Intended Scope

Over time, this module may include features for:

- audio transcription
- meeting summarization
- action item extraction
- reusable prompts and application entry points

## Current Status

This module now includes a minimal transcription flow using the OpenAI API. It supports direct transcription for shorter files, uses chunked transcription for longer files, and cleans the raw transcript into a readable version without summarizing it. The rest of the meeting workflow remains scaffold-only.

## Transcription

Audio transcription is handled through the OpenAI transcription API using the `gpt-4o-transcribe` model by default.
Raw transcription cleaning uses `gpt-4.1-mini`.

Supported formats:

- `.mp3`
- `.wav`
- `.m4a`

The transcription API now receives the original source audio. When `--debug` is enabled, the pipeline also writes a mono 16 kHz WAV comparison copy so you can inspect whether preprocessing is changing the material.

Longer files are automatically split into 10-minute chunks before transcription.
Use `--debug` to persist a full pipeline trace, including original audio, preprocessed audio, chunk audio, raw chunk transcripts, merged raw transcript, and cleaned transcript.

After transcription, the raw text is cleaned and normalized while preserving meaning.

## Required Environment Variables

- `OPENAI_API_KEY`
- `OPENAI_TRANSCRIPTION_MODEL` (optional, defaults to `gpt-4o-transcribe`)

## Local Requirement

Chunked transcription uses `pydub` for audio loading and splitting. For formats such as `.mp3` and `.m4a`, make sure `ffmpeg` is installed on your machine.

## Example Usage

```bash
make transcribe AUDIO_FILES="path/to/audio.mp3"
```

```bash
make transcribe AUDIO_FILES="path/to/audio.mp3" DEBUG_MODE=1
```

To transcribe multiple recordings in one command, pass a list of files. If the files are already stored in `meeting_assistant/audios`, you can use their names directly:

```bash
make transcribe AUDIO_FILES="Chico Ureta.m4a|Piter Moura.m4a"
```

You can also control how many files run concurrently:

```bash
make transcribe AUDIO_FILES="Chico Ureta.m4a|Piter Moura.m4a" WORKERS=2
```

The command saves the raw transcription to `meeting_assistant/outputs/transcripts/raw/<audio-file-name>.md`, the cleaned transcription to `meeting_assistant/outputs/transcripts/clean/<audio-file-name>.md`, and when `--debug` is enabled it writes a step-by-step artifact tree under `meeting_assistant/outputs/transcripts/debug/<audio-file-name>/`.

If you want to continue directly from audio files to the final Google Sheet update, use the orchestration command in the insight module:

```bash
make full-pipeline AUDIO_FILES="Chico Ureta.m4a|Piter Moura.m4a" WORKSHEET_NAME=Sheet1
```
