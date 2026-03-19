"""Minimal configuration helpers shared across assistant modules."""

from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


def get_env(name: str, default: str | None = None, required: bool = False) -> str | None:
    """Read an environment variable with an optional default and required flag."""
    value = os.getenv(name, default)

    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")

    return value
