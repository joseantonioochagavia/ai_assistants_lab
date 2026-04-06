"""Minimal configuration helpers shared across assistant modules."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def get_env(name: str, default: str | None = None, required: bool = False) -> str | None:
    """Read an environment variable with an optional default and required flag."""
    value = os.getenv(name, default)

    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")

    return value


def get_transcription_model() -> str:
    """Return the configured OpenAI transcription model."""
    return get_env("OPENAI_TRANSCRIPTION_MODEL", default="gpt-4o-transcribe") or "gpt-4o-transcribe"


def read_text_or_file(
    configured_value: str,
    *,
    setting_name: str,
    repo_root: Path,
    required: bool = False,
) -> str:
    """Return inline text or the contents of a local text file.

    If ``configured_value`` is a path that resolves to an existing file (relative
    paths are resolved against ``repo_root``), its contents are returned.
    Otherwise the raw string is returned as-is, allowing callers to pass prompt
    text directly without creating a file.
    """
    configured_value = configured_value.strip()
    if not configured_value:
        if required:
            raise RuntimeError(f"Missing required configuration: {setting_name}")
        return ""

    candidate_path = Path(configured_value).expanduser()
    if not candidate_path.is_absolute():
        candidate_path = repo_root / candidate_path

    if candidate_path.is_file():
        try:
            return candidate_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Failed to read {setting_name}: {exc}") from exc

    return configured_value
