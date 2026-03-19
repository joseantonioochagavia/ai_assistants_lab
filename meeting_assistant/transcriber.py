"""Audio transcription utilities for the meeting assistant module."""

from __future__ import annotations

import argparse
from pathlib import Path

from common.config import get_transcription_model
from common.llm_clients import create_openai_client


SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".m4a"}


def transcribe_audio(file_path: str) -> str:
    """Transcribe a supported audio file with the OpenAI transcription API."""
    audio_path = Path(file_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    if audio_path.suffix.lower() not in SUPPORTED_AUDIO_FORMATS:
        supported_formats = ", ".join(sorted(SUPPORTED_AUDIO_FORMATS))
        raise ValueError(
            f"Unsupported audio format: {audio_path.suffix or 'unknown'}. "
            f"Supported formats: {supported_formats}"
        )

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


def main() -> int:
    """Run the transcription CLI for a single audio file."""
    parser = argparse.ArgumentParser(
        description="Transcribe an audio file with the meeting assistant."
    )
    parser.add_argument("file_path", help="Path to a .mp3, .wav, or .m4a audio file.")
    args = parser.parse_args()

    try:
        print(transcribe_audio(args.file_path))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
