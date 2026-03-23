"""Transcription helpers for the meeting assistant module."""

from __future__ import annotations

import difflib
import re
import tempfile
from pathlib import Path

from common.config import get_transcription_model
from common.llm_clients import create_openai_client
from meeting_assistant.preprocess import _split_audio_into_chunks, _validate_audio_path
from meeting_assistant.save import DebugArtifacts, save_chunk_debug_transcription


MAX_DIRECT_TRANSCRIPTION_SECONDS = 1200
CHUNK_TRANSCRIPTION_SECONDS = 600
MIN_OVERLAP_CHARACTERS = 140
MIN_DUPLICATE_BLOCK_CHARACTERS = 220
MAX_OVERLAP_LINES = 40
MAX_DUPLICATE_BLOCK_LINES = 40
OVERLAP_SIMILARITY_THRESHOLD = 0.97
DUPLICATE_BLOCK_SIMILARITY_THRESHOLD = 0.995


def _split_transcript_lines(text: str) -> list[str]:
    """Return transcript units split by line breaks or sentence endings."""
    transcript_units = re.split(r"(?:\n+|(?<=[.!?])\s+)", text)
    return [unit.strip() for unit in transcript_units if unit.strip()]


def _normalize_for_comparison(text: str) -> str:
    """Normalize transcript text to compare repeated sections more reliably."""
    normalized_text = re.sub(r"[^\w\s]", " ", text.casefold())
    return re.sub(r"\s+", " ", normalized_text).strip()


def _block_text(lines: list[str]) -> str:
    """Join transcript lines into a normalized block for similarity checks."""
    return " ".join(_normalize_for_comparison(line) for line in lines).strip()


def _is_significant_overlap(lines: list[str], minimum_characters: int) -> bool:
    """Only deduplicate large enough blocks to avoid removing natural repetition."""
    return len(_block_text(lines)) >= minimum_characters


def _block_similarity(first_lines: list[str], second_lines: list[str]) -> float:
    """Return a normalized similarity score between two transcript blocks."""
    first_block = _block_text(first_lines)
    second_block = _block_text(second_lines)

    if not first_block or not second_block:
        return 0.0

    return difflib.SequenceMatcher(None, first_block, second_block).ratio()


def _remove_consecutive_duplicate_blocks(lines: list[str]) -> list[str]:
    """Collapse repeated adjacent transcript blocks that often appear in chunk output."""
    deduplicated_lines: list[str] = []
    index = 0

    while index < len(lines):
        best_block_size = 0
        max_block_size = min((len(lines) - index) // 2, MAX_DUPLICATE_BLOCK_LINES)

        for block_size in range(max_block_size, 0, -1):
            current_block = lines[index : index + block_size]
            next_block = lines[index + block_size : index + (2 * block_size)]

            if not _is_significant_overlap(current_block, MIN_DUPLICATE_BLOCK_CHARACTERS):
                continue

            if _block_similarity(current_block, next_block) >= DUPLICATE_BLOCK_SIMILARITY_THRESHOLD:
                best_block_size = block_size
                break

        if best_block_size == 0:
            deduplicated_lines.append(lines[index])
            index += 1
            continue

        block = lines[index : index + best_block_size]
        deduplicated_lines.extend(block)
        index += best_block_size

        while index + best_block_size <= len(lines):
            candidate_block = lines[index : index + best_block_size]
            if _block_similarity(block, candidate_block) < DUPLICATE_BLOCK_SIMILARITY_THRESHOLD:
                break
            index += best_block_size

    return deduplicated_lines


def _find_chunk_overlap_length(existing_lines: list[str], incoming_lines: list[str]) -> int:
    """Find the repeated suffix/prefix span between two consecutive chunk transcripts."""
    max_overlap = min(len(existing_lines), len(incoming_lines), MAX_OVERLAP_LINES)

    for overlap_length in range(max_overlap, 0, -1):
        existing_suffix = existing_lines[-overlap_length:]
        incoming_prefix = incoming_lines[:overlap_length]

        if not _is_significant_overlap(existing_suffix, MIN_OVERLAP_CHARACTERS):
            continue

        if _block_similarity(existing_suffix, incoming_prefix) >= OVERLAP_SIMILARITY_THRESHOLD:
            return overlap_length

    return 0


def merge_chunk_transcriptions(chunk_transcriptions: list[str]) -> str:
    """Merge chunk transcripts into one transcript while removing duplicate sections."""
    merged_lines: list[str] = []

    for chunk_text in chunk_transcriptions:
        chunk_lines = _remove_consecutive_duplicate_blocks(_split_transcript_lines(chunk_text))
        if not chunk_lines:
            continue

        if not merged_lines:
            merged_lines.extend(chunk_lines)
            continue

        overlap_length = _find_chunk_overlap_length(merged_lines, chunk_lines)
        merged_lines.extend(chunk_lines[overlap_length:])

    return "\n".join(merged_lines).strip()


def transcribe_audio(file_path: str) -> str:
    """Transcribe a supported audio file with the OpenAI transcription API."""
    audio_path = _validate_audio_path(file_path)

    client = create_openai_client()
    model = get_transcription_model()

    try:
        with audio_path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
            )
    except Exception as exc:
        raise RuntimeError(f"OpenAI transcription failed: {exc}") from exc

    return response.text


def _transcribe_chunk_sequence(
    chunk_metadata,
    *,
    source_file_path: str,
    debug_artifacts: DebugArtifacts | None = None,
) -> str:
    """Transcribe a sequence of chunk files and optionally persist debug outputs."""
    chunk_transcriptions: list[str] = []

    for chunk in chunk_metadata:
        try:
            chunk_transcription = transcribe_audio(str(chunk.path)).strip()
        except RuntimeError as exc:
            raise RuntimeError(
                f"Failed during transcription of chunk {chunk.index}: {exc}"
            ) from exc

        if debug_artifacts is not None:
            save_chunk_debug_transcription(
                source_file_path,
                chunk.index,
                chunk.start_ms,
                chunk.end_ms,
                chunk_transcription,
                output_dir=debug_artifacts.chunk_transcript_dir,
                chunk_file_name=chunk.path.name,
            )

        chunk_transcriptions.append(chunk_transcription)

    return merge_chunk_transcriptions(chunk_transcriptions)


def transcribe_audio_in_chunks(
    file_path: str,
    *,
    debug_source_path: str | None = None,
    debug_artifacts: DebugArtifacts | None = None,
) -> str:
    """Transcribe an audio file by splitting it into smaller chunks first."""
    audio_path = _validate_audio_path(file_path)
    source_file_path = debug_source_path or str(audio_path)

    if debug_artifacts is not None:
        chunk_metadata = _split_audio_into_chunks(
            str(audio_path),
            chunk_duration_seconds=CHUNK_TRANSCRIPTION_SECONDS,
            output_dir=debug_artifacts.chunk_audio_dir,
        )
        return _transcribe_chunk_sequence(
            chunk_metadata,
            source_file_path=source_file_path,
            debug_artifacts=debug_artifacts,
        )

    with tempfile.TemporaryDirectory(prefix="meeting-assistant-chunks-") as temp_dir:
        chunk_metadata = _split_audio_into_chunks(
            str(audio_path),
            chunk_duration_seconds=CHUNK_TRANSCRIPTION_SECONDS,
            output_dir=Path(temp_dir),
        )
        return _transcribe_chunk_sequence(
            chunk_metadata,
            source_file_path=source_file_path,
        )
