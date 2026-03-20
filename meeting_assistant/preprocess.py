"""Audio preprocessing utilities for the meeting assistant module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".m4a"}
EXPORT_FORMAT_BY_SUFFIX = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".m4a": "mp4",
}
PREPROCESSED_AUDIO_FORMAT = "wav"
PREPROCESSED_SAMPLE_RATE_HZ = 16000
PREPROCESSED_CHANNELS = 1
CHUNK_OVERLAP_SECONDS = 30


@dataclass(frozen=True)
class AudioChunk:
    """Metadata for an exported audio chunk."""

    index: int
    start_ms: int
    end_ms: int
    path: Path


def _validate_audio_path(file_path: str) -> Path:
    """Return a validated audio path or raise a clear error."""
    audio_path = Path(file_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_FORMATS:
        supported_formats = ", ".join(sorted(SUPPORTED_AUDIO_FORMATS))
        raise ValueError(
            f"Unsupported audio format: {audio_path.suffix or 'unknown'}. "
            f"Supported formats: {supported_formats}"
        )

    return audio_path


def _load_audio_segment(file_path: str):
    """Load an audio file with pydub for duration checks, preprocessing, and chunking."""
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise RuntimeError(
            "Audio processing dependencies are missing. Install project requirements first."
        ) from exc

    audio_path = _validate_audio_path(file_path)

    try:
        return AudioSegment.from_file(audio_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to read audio metadata: {exc}") from exc


def get_audio_duration_seconds(file_path: str) -> float:
    """Return the audio duration in seconds."""
    audio = _load_audio_segment(file_path)
    return len(audio) / 1000.0


def preprocess_audio_for_transcription(file_path: str, output_dir: Path) -> Path:
    """Create a conservative WAV copy before sending audio to the transcription API."""
    audio_path = _validate_audio_path(file_path)
    processed_audio = _load_audio_segment(str(audio_path))

    # Keep preprocessing intentionally light so we preserve the full recording.
    processed_audio = processed_audio.set_channels(PREPROCESSED_CHANNELS)
    processed_audio = processed_audio.set_frame_rate(PREPROCESSED_SAMPLE_RATE_HZ)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{audio_path.stem}_preprocessed.{PREPROCESSED_AUDIO_FORMAT}"

    try:
        processed_audio.export(output_path, format=PREPROCESSED_AUDIO_FORMAT)
    except Exception as exc:
        raise RuntimeError(f"Failed to preprocess audio: {exc}") from exc

    return output_path


def _split_audio_into_chunks(
    file_path: str, chunk_duration_seconds: int, output_dir: Path
) -> list[AudioChunk]:
    """Split an audio file into chunk files inside the provided directory."""
    audio = _load_audio_segment(file_path)
    audio_path = _validate_audio_path(file_path)
    chunk_duration_ms = chunk_duration_seconds * 1000
    chunk_overlap_ms = CHUNK_OVERLAP_SECONDS * 1000
    export_format = EXPORT_FORMAT_BY_SUFFIX[audio_path.suffix.lower()]
    chunk_step_ms = chunk_duration_ms - chunk_overlap_ms
    chunk_metadata: list[AudioChunk] = []

    if chunk_step_ms <= 0:
        raise ValueError("Chunk overlap must be smaller than chunk duration.")

    start_ms = 0
    chunk_index = 1

    while start_ms < len(audio):
        end_ms = min(start_ms + chunk_duration_ms, len(audio))
        chunk = audio[start_ms:end_ms]
        chunk_path = output_dir / f"{audio_path.stem}_chunk_{chunk_index:03d}{audio_path.suffix.lower()}"

        try:
            chunk.export(chunk_path, format=export_format)
        except Exception as exc:
            raise RuntimeError(f"Failed to split audio into chunks: {exc}") from exc

        chunk_metadata.append(
            AudioChunk(
                index=chunk_index,
                start_ms=start_ms,
                end_ms=end_ms,
                path=chunk_path,
            )
        )

        if end_ms >= len(audio):
            break

        start_ms += chunk_step_ms
        chunk_index += 1

    return chunk_metadata
