"""End-to-end CLI for audio transcription through Google Sheets export."""

from __future__ import annotations

import argparse
from pathlib import Path

from insight_engine.data_extraction import extract_structured_data_from_files
from insight_engine.export_data_to_google_sheet import (
    DEFAULT_WORKSHEET_NAME,
    export_dataframe_to_google_sheet,
)
from insight_engine.insight_engine import (
    build_refined_insight_dataframe,
)
from insight_engine.refinement_engine import get_refinement_metadata
from meeting_assistant.app import transcribe_multiple_audio_files


def run_full_pipeline(
    audio_paths: list[str],
    *,
    debug: bool = False,
    max_workers: int | None = None,
    worksheet_name: str = DEFAULT_WORKSHEET_NAME,
    spreadsheet_id: str | None = None,
    service_account_json_path: str | None = None,
) -> tuple[str, object]:
    """Transcribe selected audio files, build the refined table, and export it."""
    successes, failures = transcribe_multiple_audio_files(
        audio_paths,
        debug=debug,
        max_workers=max_workers,
    )

    if failures:
        failure_lines = [f"{input_name}: {exc}" for input_name, exc in failures]
        raise RuntimeError(
            "Full pipeline aborted because one or more audio files failed:\n"
            + "\n".join(failure_lines)
        )

    cleaned_transcript_paths = [output_path for _, _, output_path in successes]
    structured_data = extract_structured_data_from_files(cleaned_transcript_paths)
    refined_dataframe = build_refined_insight_dataframe(structured_data)
    export_summary = export_dataframe_to_google_sheet(
        refined_dataframe,
        worksheet_name=worksheet_name,
        spreadsheet_id=spreadsheet_id,
        service_account_json_path=service_account_json_path,
    )
    return export_summary, refined_dataframe


def main() -> int:
    """Run the full audio -> transcripts -> insights -> Google Sheets pipeline."""
    parser = argparse.ArgumentParser(
        description="Run the full pipeline from audio files to Google Sheets export."
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
        help="Persist transcription debug artifacts for inspection.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Maximum number of files to transcribe concurrently.",
    )
    parser.add_argument(
        "--worksheet-name",
        default=DEFAULT_WORKSHEET_NAME,
        help="Worksheet name to use when exporting to Google Sheets.",
    )
    parser.add_argument(
        "--spreadsheet-id",
        help="Optional Google Sheets spreadsheet ID or URL override.",
    )
    parser.add_argument(
        "--service-account-json-path",
        help="Optional Google service account JSON path override.",
    )
    args = parser.parse_args()

    try:
        export_summary, refined_dataframe = run_full_pipeline(
            args.file_paths,
            debug=args.debug,
            max_workers=args.workers,
            worksheet_name=args.worksheet_name,
            spreadsheet_id=args.spreadsheet_id,
            service_account_json_path=args.service_account_json_path,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    for input_name in args.file_paths:
        resolved_name = Path(input_name).name
        print(f"{resolved_name}: processed successfully")

    refinement_metadata = get_refinement_metadata(refined_dataframe)
    if refinement_metadata.get("scores"):
        scores = " -> ".join(str(score) for score in refinement_metadata["scores"])
        print(
            "Refinement completed successfully "
            f"(scores: {scores}, best: {refinement_metadata['best_score']})."
        )

    print(export_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
