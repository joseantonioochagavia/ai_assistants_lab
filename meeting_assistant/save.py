"""Transcript output helpers for the meeting assistant module."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from meeting_assistant.preprocess import _validate_audio_path


OUTPUTS_DIR = Path(__file__).resolve().parent / "outputs" / "transcripts"
RAW_OUTPUTS_DIR = OUTPUTS_DIR / "raw"
CLEAN_OUTPUTS_DIR = OUTPUTS_DIR / "clean"
DEBUG_OUTPUTS_DIR = OUTPUTS_DIR / "debug"


@dataclass(frozen=True)
class DebugArtifacts:
    """Filesystem layout for a single debug transcription run."""

    root_dir: Path
    original_audio_dir: Path
    preprocessed_audio_dir: Path
    chunk_audio_dir: Path
    transcript_dir: Path
    chunk_transcript_dir: Path


def get_debug_artifacts(file_path: str) -> DebugArtifacts:
    """Return the debug artifact layout for a source audio file."""
    audio_path = _validate_audio_path(file_path)
    root_dir = DEBUG_OUTPUTS_DIR / audio_path.stem

    return DebugArtifacts(
        root_dir=root_dir,
        original_audio_dir=root_dir / "audio" / "original",
        preprocessed_audio_dir=root_dir / "audio" / "preprocessed",
        chunk_audio_dir=root_dir / "audio" / "chunks",
        transcript_dir=root_dir / "transcripts",
        chunk_transcript_dir=root_dir / "transcripts" / "chunks",
    )


def prepare_debug_artifacts(file_path: str) -> DebugArtifacts:
    """Create a clean debug artifact directory for the provided source file."""
    debug_artifacts = get_debug_artifacts(file_path)

    try:
        if debug_artifacts.root_dir.exists():
            shutil.rmtree(debug_artifacts.root_dir)

        for directory in (
            debug_artifacts.original_audio_dir,
            debug_artifacts.preprocessed_audio_dir,
            debug_artifacts.chunk_audio_dir,
            debug_artifacts.transcript_dir,
            debug_artifacts.chunk_transcript_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Failed while preparing debug outputs: {exc}") from exc

    return debug_artifacts


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


def save_debug_audio_artifact(
    source_path: str | Path,
    output_dir: Path,
    output_name: str | None = None,
) -> Path:
    """Copy an audio artifact into the debug output tree."""
    source_audio_path = Path(source_path)
    output_path = output_dir / (output_name or source_audio_path.name)

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_audio_path, output_path)
    except OSError as exc:
        raise RuntimeError(f"Failed while saving debug audio artifact: {exc}") from exc

    return output_path


def _save_debug_transcription_markdown(
    transcription: str,
    output_path: Path,
    title: str,
    source_file_name: str,
    metadata_lines: list[str] | None = None,
) -> Path:
    """Save a debug transcript stage to a markdown file."""
    metadata_section = ""
    if metadata_lines:
        metadata_section = "\n".join(metadata_lines) + "\n\n"

    markdown = (
        f"# {title}\n\n"
        f"Source file: {source_file_name}\n\n"
        f"{metadata_section}"
        "---\n\n"
        f"{transcription.strip()}\n"
    )

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
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
    output_dir: Path | None = None,
    chunk_file_name: str | None = None,
) -> Path:
    """Save the raw transcription output for a single chunk."""
    audio_path = _validate_audio_path(file_path)
    chunk_output_dir = output_dir or (DEBUG_OUTPUTS_DIR / audio_path.stem / "transcripts" / "chunks")
    output_path = chunk_output_dir / f"chunk_{chunk_index:03d}.md"
    metadata_lines = [
        f"Chunk index: {chunk_index}",
        f"Start ms: {start_ms}",
        f"End ms: {end_ms}",
    ]
    if chunk_file_name:
        metadata_lines.append(f"Chunk file: {chunk_file_name}")

    return _save_debug_transcription_markdown(
        transcription=transcription,
        output_path=output_path,
        title="Chunk Transcription",
        source_file_name=audio_path.name,
        metadata_lines=metadata_lines,
    )


def save_merged_raw_debug_transcription(
    file_path: str,
    transcription: str,
    output_path: Path | None = None,
) -> Path:
    """Save the merged raw transcript before the cleaning step."""
    audio_path = _validate_audio_path(file_path)
    merged_output_path = output_path or (
        DEBUG_OUTPUTS_DIR / audio_path.stem / "transcripts" / "merged_raw.md"
    )

    return _save_debug_transcription_markdown(
        transcription=transcription,
        output_path=merged_output_path,
        title="Merged Raw Transcription",
        source_file_name=audio_path.name,
    )


def save_cleaned_debug_transcription(
    file_path: str,
    transcription: str,
    output_path: Path | None = None,
) -> Path:
    """Save the cleaned transcript into the debug output tree."""
    audio_path = _validate_audio_path(file_path)
    cleaned_output_path = output_path or (
        DEBUG_OUTPUTS_DIR / audio_path.stem / "transcripts" / "cleaned.md"
    )

    return _save_debug_transcription_markdown(
        transcription=transcription,
        output_path=cleaned_output_path,
        title="Cleaned Transcription",
        source_file_name=audio_path.name,
    )
