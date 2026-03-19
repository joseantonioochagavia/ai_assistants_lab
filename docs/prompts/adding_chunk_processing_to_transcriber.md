# Prompt: Add chunked transcription support and save output to markdown

Update the `meeting_assistant` transcription flow in the `ai_assistants_lab` repository to support long audio files by splitting them into chunks before sending them to the OpenAI transcription API.

## Context

The current implementation uses OpenAI transcription with `gpt-4o-transcribe` and works for shorter files, but fails for long audio due to model duration limits.

Example real error returned by the API:

"audio duration 2687.053125 seconds is longer than 1400 seconds which is the maximum for this model"

We now need a more robust first iteration that automatically handles long audio files.

## Goal

Implement a new function called:

"def transcribe_audio_in_chunks(file_path: str) -> str:"

and update the transcription flow so that:
- and update the transcription flow so that:
- if the audio is short enough, use transcribe_audio(file_path)

Also save the final transcription into a .md file inside outputs/transcripts folder.

## Important constraints

- Keep implementation simple and readable
- Do not overengineer
- Keep public-repo friendly
- Keep public-repo friendly
- Do not add unrelated features
- Do not implement summarization yet
- Python 3.10+

## Chunking requirements

- Use a safe chunk size below the API maximum
- Use a safe chunk size below the API maximum
- Do NOT use 30-minute chunk
- Use a safer default such as 1200 seconds (20 minutes)

## Audio duration detection
Add a helper to detect audio duration before choosing transcription strategy.

## Markdown output format

Keep it simple, for example:
"
Transcription

Source file: Samuel Hurtado.m4a

---

[full transcription here]
"

## CLI behavior:

If the module already supports CLI execution, update it so that:
"python -m meeting_assistant.transcriber path/to/audio.m4a"
will:
- automatically decide between direct transcription or chunked transcription
- automatically decide between direct transcription or chunked transcription
- print a short success message

## Dependencies
Add only the minimum necessary dependencies to support:
- audio duration detection
- audio splitting

Choose a practical and common solution

Keep dependencies minimal.

## Error handling
Add clear errors for:
- file not found
- file not found
- unsupported extension
- failure to read audio metadata
- failure during transcription
- failure while saving output file