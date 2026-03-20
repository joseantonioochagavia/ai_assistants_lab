"""Application entry point for the meeting assistant transcription flow."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from meeting_assistant.clean import clean_transcription
from meeting_assistant.preprocess import (
    _validate_audio_path,
    get_audio_duration_seconds,
    preprocess_audio_for_transcription,
)
from meeting_assistant.save import CLEAN_OUTPUTS_DIR, RAW_OUTPUTS_DIR, save_transcription_markdown
from meeting_assistant.transcribe import (
    MAX_DIRECT_TRANSCRIPTION_SECONDS,
    transcribe_audio,
    transcribe_audio_in_chunks,
)


def transcribe_audio_file(file_path: str) -> tuple[str, Path]:
    """Choose a transcription strategy, then save the result to markdown."""
    audio_path = _validate_audio_path(file_path)

    with tempfile.TemporaryDirectory(prefix="meeting-assistant-audio-") as temp_dir:
        preprocessed_audio_path = preprocess_audio_for_transcription(
            str(audio_path),
            output_dir=Path(temp_dir),
        )
        duration_seconds = get_audio_duration_seconds(str(preprocessed_audio_path))

        if duration_seconds <= MAX_DIRECT_TRANSCRIPTION_SECONDS:
            raw_transcription = transcribe_audio(str(preprocessed_audio_path))
        else:
            raw_transcription = transcribe_audio_in_chunks(str(preprocessed_audio_path))

    cleaned_transcription = clean_transcription(raw_transcription)
    save_transcription_markdown(
        str(audio_path),
        raw_transcription,
        output_dir=RAW_OUTPUTS_DIR,
    )
    clean_output_path = save_transcription_markdown(
        str(audio_path),
        cleaned_transcription,
        output_dir=CLEAN_OUTPUTS_DIR,
    )
    return cleaned_transcription, clean_output_path


def main() -> int:
    """Run the transcription CLI for a single audio file."""
    parser = argparse.ArgumentParser(
        description="Transcribe an audio file with the meeting assistant."
    )
    parser.add_argument("file_path", help="Path to a .mp3, .wav, or .m4a audio file.")
    args = parser.parse_args()

    try:
        _, output_path = transcribe_audio_file(args.file_path)
        print(f"Transcription saved to {output_path}")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
