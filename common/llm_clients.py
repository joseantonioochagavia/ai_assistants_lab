"""Client factories for LLM providers used across the repository."""

from __future__ import annotations

from openai import OpenAI

from common.config import get_env


def create_openai_client(api_key: str | None = None) -> OpenAI:
    """Create a minimal OpenAI client instance for future assistant modules."""
    resolved_api_key = api_key or get_env("OPENAI_API_KEY", required=True)
    return OpenAI(api_key=resolved_api_key)
