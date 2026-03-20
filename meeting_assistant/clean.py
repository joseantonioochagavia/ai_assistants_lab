"""Transcription cleaning helpers for the meeting assistant module."""

from __future__ import annotations

from common.llm_clients import create_openai_client


CLEAN_TRANSCRIPTION_MODEL = "gpt-4.1-mini"
CLEAN_TRANSCRIPTION_SYSTEM_PROMPT = """You are an expert transcription editor.

Your task is to clean and normalize raw meeting transcriptions.

Rules:
- Preserve the original meaning exactly
- Do NOT summarize
- Do NOT remove important content
- Do NOT add new information

You must:
- Fix grammar and spelling
- Remove filler words (e.g., "eh", "mmm", "like", "weon" only if used as filler)
- Improve sentence structure
- Separate ideas into clear sentences or paragraphs
- Make the text readable and professional

Output:
- Return ONLY the cleaned text
- Do not include explanations
"""


def clean_transcription(raw_text: str) -> str:
    """Clean a raw transcription without changing its meaning."""
    if not raw_text.strip():
        return ""

    client = create_openai_client()

    try:
        response = client.chat.completions.create(
            model=CLEAN_TRANSCRIPTION_MODEL,
            messages=[
                {"role": "system", "content": CLEAN_TRANSCRIPTION_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            temperature=0.2,
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI transcription cleaning failed: {exc}") from exc

    cleaned_text = response.choices[0].message.content
    return (cleaned_text or "").strip()
