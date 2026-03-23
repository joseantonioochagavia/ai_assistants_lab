"""Application entry point for the meeting assistant transcription flow."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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

AUDIOS_DIR = Path(__file__).resolve().parent / "audios"
DEFAULT_BATCH_WORKERS = 4


def _resolve_audio_input(file_path: str) -> Path:
    """Resolve a CLI audio input from an explicit path or the module audios directory."""
    audio_path = Path(file_path)

    if audio_path.is_file():
        return _validate_audio_path(str(audio_path))

    if not audio_path.is_absolute() and len(audio_path.parts) == 1:
        bundled_audio_path = AUDIOS_DIR / audio_path.name
        if bundled_audio_path.is_file():
            return _validate_audio_path(str(bundled_audio_path))

    return _validate_audio_path(file_path)


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
    audio_path = _resolve_audio_input(file_path)

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


def transcribe_multiple_audio_files(
    file_paths: list[str],
    *,
    debug: bool = False,
    max_workers: int | None = None,
) -> tuple[list[tuple[str, Path, Path]], list[tuple[str, Exception]]]:
    """Transcribe multiple audio files concurrently and preserve input order in the report."""
    if max_workers is not None and max_workers < 1:
        raise ValueError("--workers must be at least 1.")

    resolved_inputs: list[tuple[str, Path]] = []
    failures_by_input: dict[str, Exception] = {}

    for file_path in file_paths:
        try:
            resolved_inputs.append((file_path, _resolve_audio_input(file_path)))
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            failures_by_input[file_path] = exc

    if not resolved_inputs:
        return [], [(file_path, failures_by_input[file_path]) for file_path in file_paths]

    worker_count = min(max_workers or DEFAULT_BATCH_WORKERS, len(resolved_inputs))
    outputs_by_input: dict[str, tuple[Path, Path]] = {}

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_input = {
            executor.submit(transcribe_audio_file, str(audio_path), debug=debug): (file_path, audio_path)
            for file_path, audio_path in resolved_inputs
        }

        for future in as_completed(future_to_input):
            file_path, audio_path = future_to_input[future]
            try:
                _, output_path = future.result()
            except (FileNotFoundError, ValueError, RuntimeError) as exc:
                failures_by_input[file_path] = exc
                continue

            outputs_by_input[file_path] = (audio_path, output_path)

    successes = [
        (file_path, outputs_by_input[file_path][0], outputs_by_input[file_path][1])
        for file_path in file_paths
        if file_path in outputs_by_input
    ]
    failures = [
        (file_path, failures_by_input[file_path])
        for file_path in file_paths
        if file_path in failures_by_input
    ]
    return successes, failures


def main() -> int:
    """Run the transcription CLI for one or more audio files."""
    parser = argparse.ArgumentParser(
        description="Transcribe one or more audio files with the meeting assistant."
    )
    parser.add_argument(
        "file_paths",
        nargs="+",
        help=(
            "Path(s) to .mp3, .wav, or .m4a audio files. "
            "Bare file names are also resolved from meeting_assistant/audios."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Persist pipeline artifacts for step-by-step inspection.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Maximum number of files to transcribe concurrently.",
    )
    args = parser.parse_args()

    if len(args.file_paths) == 1:
        try:
            resolved_audio_path = _resolve_audio_input(args.file_paths[0])
            _, output_path = transcribe_audio_file(str(resolved_audio_path), debug=args.debug)
            print(f"Transcription saved to {output_path}")
            if args.debug:
                print(f"Debug artifacts saved to {get_debug_artifacts(str(resolved_audio_path)).root_dir}")
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise SystemExit(str(exc)) from exc

        return 0

    try:
        successes, failures = transcribe_multiple_audio_files(
            args.file_paths,
            debug=args.debug,
            max_workers=args.workers,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    for input_name, resolved_audio_path, output_path in successes:
        print(f"{input_name}: transcription saved to {output_path}")
        if args.debug:
            print(f"{input_name}: debug artifacts saved to {get_debug_artifacts(str(resolved_audio_path)).root_dir}")

    for input_name, exc in failures:
        print(f"{input_name}: {exc}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
