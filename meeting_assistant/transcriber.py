"""Audio transcription utilities for the meeting assistant module."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from common.config import get_transcription_model
from common.llm_clients import create_openai_client


SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".m4a"}
MAX_DIRECT_TRANSCRIPTION_SECONDS = 1200
OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "transcripts"
EXPORT_FORMAT_BY_SUFFIX = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".m4a": "mp4",
}


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
    """Load an audio file with pydub for duration checks and chunking."""
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise RuntimeError(
            "Audio chunking dependencies are missing. Install project requirements first."
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


def _split_audio_into_chunks(
    file_path: str, chunk_duration_seconds: int, output_dir: Path
) -> list[Path]:
    """Split an audio file into chunk files inside the provided directory."""
    audio = _load_audio_segment(file_path)
    audio_path = _validate_audio_path(file_path)
    chunk_duration_ms = chunk_duration_seconds * 1000
    export_format = EXPORT_FORMAT_BY_SUFFIX[audio_path.suffix.lower()]
    chunk_paths: list[Path] = []

    for chunk_index, start_ms in enumerate(range(0, len(audio), chunk_duration_ms), start=1):
        chunk = audio[start_ms : start_ms + chunk_duration_ms]
        chunk_path = output_dir / f"{audio_path.stem}_chunk_{chunk_index:03d}{audio_path.suffix.lower()}"

        try:
            chunk.export(chunk_path, format=export_format)
        except Exception as exc:
            raise RuntimeError(f"Failed to split audio into chunks: {exc}") from exc

        chunk_paths.append(chunk_path)

    return chunk_paths


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


def transcribe_audio_in_chunks(file_path: str) -> str:
    """Transcribe an audio file by splitting it into smaller chunks first."""
    audio_path = _validate_audio_path(file_path)
    chunk_transcriptions: list[str] = []

    with tempfile.TemporaryDirectory(prefix="meeting-assistant-chunks-") as temp_dir:
        chunk_paths = _split_audio_into_chunks(
            str(audio_path),
            chunk_duration_seconds=MAX_DIRECT_TRANSCRIPTION_SECONDS,
            output_dir=Path(temp_dir),
        )

        for chunk_index, chunk_path in enumerate(chunk_paths, start=1):
            try:
                chunk_transcriptions.append(transcribe_audio(str(chunk_path)).strip())
            except RuntimeError as exc:
                raise RuntimeError(
                    f"Failed during transcription of chunk {chunk_index}: {exc}"
                ) from exc

    return "\n\n".join(text for text in chunk_transcriptions if text).strip()


def save_transcription_markdown(file_path: str, transcription: str) -> Path:
    """Save a transcription to the repository transcripts output directory."""
    audio_path = _validate_audio_path(file_path)
    output_path = OUTPUTS_DIR / f"{audio_path.stem}.md"
    markdown = (
        "# Transcription\n\n"
        f"Source file: {audio_path.name}\n\n"
        "---\n\n"
        f"{transcription.strip()}\n"
    )

    try:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed while saving output file: {exc}") from exc

    return output_path


def transcribe_audio_file(file_path: str) -> tuple[str, Path]:
    """Choose a transcription strategy, then save the result to markdown."""
    duration_seconds = get_audio_duration_seconds(file_path)

    if duration_seconds <= MAX_DIRECT_TRANSCRIPTION_SECONDS:
        transcription = transcribe_audio(file_path)
    else:
        transcription = transcribe_audio_in_chunks(file_path)

    output_path = save_transcription_markdown(file_path, transcription)
    return transcription, output_path


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
