"""Transcript output helpers for the meeting assistant module."""

from __future__ import annotations

from pathlib import Path

from meeting_assistant.preprocess import _validate_audio_path


OUTPUTS_DIR = Path(__file__).resolve().parent / "outputs" / "transcripts"
RAW_OUTPUTS_DIR = OUTPUTS_DIR / "raw"
CLEAN_OUTPUTS_DIR = OUTPUTS_DIR / "clean"
DEBUG_OUTPUTS_DIR = OUTPUTS_DIR / "debug"


def save_transcription_markdown(
    file_path: str,
    transcription: str,
    output_dir: Path = CLEAN_OUTPUTS_DIR,
) -> Path:
    """Save a transcription to the repository transcripts output directory."""
    audio_path = _validate_audio_path(file_path)
    output_path = output_dir / f"{audio_path.stem}.md"
    markdown = (
        "# Transcription\n\n"
        f"Source file: {audio_path.name}\n\n"
        "---\n\n"
        f"{transcription.strip()}\n"
    )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed while saving output file: {exc}") from exc

    return output_path


def save_chunk_debug_transcription(
    file_path: str,
    chunk_index: int,
    start_ms: int,
    end_ms: int,
    transcription: str,
) -> Path:
    """Save the raw transcription output for a single chunk."""
    audio_path = _validate_audio_path(file_path)
    output_dir = DEBUG_OUTPUTS_DIR / audio_path.stem / "chunks"
    output_path = output_dir / f"chunk_{chunk_index:03d}.md"
    markdown = (
        "# Chunk Transcription\n\n"
        f"Source file: {audio_path.name}\n\n"
        f"Chunk index: {chunk_index}\n"
        f"Start ms: {start_ms}\n"
        f"End ms: {end_ms}\n\n"
        "---\n\n"
        f"{transcription.strip()}\n"
    )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed while saving output file: {exc}") from exc

    return output_path


def save_merged_raw_debug_transcription(file_path: str, transcription: str) -> Path:
    """Save the merged raw transcript before the cleaning step."""
    audio_path = _validate_audio_path(file_path)
    output_dir = DEBUG_OUTPUTS_DIR / audio_path.stem
    output_path = output_dir / "merged_raw.md"
    markdown = (
        "# Merged Raw Transcription\n\n"
        f"Source file: {audio_path.name}\n\n"
        "---\n\n"
        f"{transcription.strip()}\n"
    )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed while saving output file: {exc}") from exc

    return output_path
