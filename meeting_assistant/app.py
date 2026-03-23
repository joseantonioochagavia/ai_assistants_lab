"""Application entry point for the meeting assistant transcription flow."""

from __future__ import annotations

import argparse
from pathlib import Path

from meeting_assistant.clean import clean_transcription
from meeting_assistant.preprocess import (
    _validate_audio_path,
    get_audio_duration_seconds,
    preprocess_audio_for_transcription,
)
from meeting_assistant.save import (
    CLEAN_OUTPUTS_DIR,
    RAW_OUTPUTS_DIR,
    get_debug_artifacts,
    prepare_debug_artifacts,
    save_cleaned_debug_transcription,
    save_debug_audio_artifact,
    save_merged_raw_debug_transcription,
    save_transcription_markdown,
)
from meeting_assistant.transcribe import (
    MAX_DIRECT_TRANSCRIPTION_SECONDS,
    transcribe_audio,
    transcribe_audio_in_chunks,
)


def _transcribe_audio_for_pipeline(source_audio_path: Path, *, debug: bool) -> str:
    """Transcribe the source audio using the appropriate strategy."""
    duration_seconds = get_audio_duration_seconds(str(source_audio_path))

    if duration_seconds <= MAX_DIRECT_TRANSCRIPTION_SECONDS:
        return transcribe_audio(str(source_audio_path))

    if not debug:
        return transcribe_audio_in_chunks(str(source_audio_path))

    debug_artifacts = get_debug_artifacts(str(source_audio_path))
    return transcribe_audio_in_chunks(
        str(source_audio_path),
        debug_source_path=str(source_audio_path),
        debug_artifacts=debug_artifacts,
    )


def transcribe_audio_file(file_path: str, *, debug: bool = False) -> tuple[str, Path]:
    """Choose a transcription strategy, then save the result to markdown."""
    audio_path = _validate_audio_path(file_path)

    if debug:
        debug_artifacts = prepare_debug_artifacts(str(audio_path))
        save_debug_audio_artifact(audio_path, debug_artifacts.original_audio_dir)
        preprocess_audio_for_transcription(
            str(audio_path),
            output_dir=debug_artifacts.preprocessed_audio_dir,
        )

    raw_transcription = _transcribe_audio_for_pipeline(audio_path, debug=debug)

    cleaned_transcription = clean_transcription(raw_transcription)

    if debug:
        debug_artifacts = get_debug_artifacts(str(audio_path))
        save_merged_raw_debug_transcription(
            str(audio_path),
            raw_transcription,
            output_path=debug_artifacts.transcript_dir / "merged_raw.md",
        )
        save_cleaned_debug_transcription(
            str(audio_path),
            cleaned_transcription,
            output_path=debug_artifacts.transcript_dir / "cleaned.md",
        )

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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Persist pipeline artifacts for step-by-step inspection.",
    )
    args = parser.parse_args()

    try:
        _, output_path = transcribe_audio_file(args.file_path, debug=args.debug)
        print(f"Transcription saved to {output_path}")
        if args.debug:
            print(f"Debug artifacts saved to {get_debug_artifacts(args.file_path).root_dir}")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
