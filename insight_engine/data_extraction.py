"""Structured extraction helpers for the insight engine module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.config import get_env
from common.llm_clients import create_openai_client


DEFAULT_TRANSCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "meeting_assistant"
    / "outputs"
    / "transcripts"
    / "clean"
)
DEFAULT_EXTRACTION_MODEL = "gpt-4.1-mini"
STRUCTURED_EXTRACTION_SYSTEM_PROMPT = """You extract structured business information from cleaned meeting transcripts.

Return valid JSON only.
Do not include markdown fences, explanations, or extra keys.
Keep the extracted items concise and faithful to the transcript.
"""
PAIN_EXTRACTION_TASK_PROMPT = """You are analyzing a meeting transcript.

Your task is to identify concrete pain points, frustrations, bottlenecks, or unmet needs explicitly or implicitly mentioned in the conversation.

Return a JSON object with exactly this structure:
{"dolores": ["pain 1", "pain 2"]}

Rules:
- Include only pains grounded in the transcript (do not invent or infer beyond the text)
- Write all pain points in Spanish
- Each pain must be clear, specific, and written as a normalized statement (not raw quotes)
- Avoid filler words or conversational language
- Do not repeat similar pains (deduplicate when necessary)
- If no pain points are present, return: {"dolores": []}

Output constraints:
- Return ONLY valid JSON
- Do not include explanations, comments, or additional text
"""


def get_structured_extraction_model() -> str:
    """Return the configured model for insight extraction."""
    return get_env("OPENAI_DATA_EXTRACTION_MODEL", default=DEFAULT_EXTRACTION_MODEL) or DEFAULT_EXTRACTION_MODEL


def read_transcript_markdown(file_path: str | Path) -> str:
    """Read a cleaned transcript markdown file and return only the transcript body."""
    transcript_path = Path(file_path)

    try:
        markdown = transcript_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Failed to read transcript file: {exc}") from exc

    parts = markdown.split("\n---\n", maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()

    return markdown


def _strip_json_fence(content: str) -> str:
    """Remove optional markdown fences around JSON output."""
    cleaned_content = content.strip()

    if cleaned_content.startswith("```"):
        cleaned_content = cleaned_content.removeprefix("```json").removeprefix("```").strip()
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3].strip()

    return cleaned_content


def _parse_structured_response(content: str) -> dict[str, list[str]]:
    """Parse the JSON response from the extraction model."""
    try:
        payload = json.loads(_strip_json_fence(content))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse structured extraction output: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Structured extraction output must be a JSON object.")

    pains = payload.get("dolores", [])
    if not isinstance(pains, list):
        raise RuntimeError('Structured extraction output must include a "dolores" list.')

    normalized_pains = [str(item).strip() for item in pains if str(item).strip()]
    return {"dolores": normalized_pains}


def extract_structured_fields(
    transcript_text: str,
    *,
    system_prompt: str = STRUCTURED_EXTRACTION_SYSTEM_PROMPT,
    task_prompt: str = PAIN_EXTRACTION_TASK_PROMPT,
    model: str | None = None,
) -> dict[str, list[str]]:
    """Extract structured fields from a single transcript using a configurable prompt."""
    if not transcript_text.strip():
        return {"dolores": []}

    client = create_openai_client()
    resolved_model = model or get_structured_extraction_model()

    try:
        response = client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"{task_prompt}\n\nTranscript:\n{transcript_text}",
                },
            ],
            temperature=0.2,
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI structured extraction failed: {exc}") from exc

    response_text = response.choices[0].message.content or ""
    return _parse_structured_response(response_text)


def extract_structured_data(
    input_dir: str | Path = DEFAULT_TRANSCRIPTS_DIR,
    *,
    system_prompt: str = STRUCTURED_EXTRACTION_SYSTEM_PROMPT,
    task_prompt: str = PAIN_EXTRACTION_TASK_PROMPT,
    model: str | None = None,
) -> list[dict[str, object]]:
    """Extract meeting-level structured data from all cleaned transcripts in a directory."""
    transcripts_dir = Path(input_dir)

    if not transcripts_dir.is_dir():
        raise FileNotFoundError(f"Transcript directory not found: {transcripts_dir}")

    structured_data: list[dict[str, object]] = []

    for transcript_path in sorted(transcripts_dir.glob("*.md")):
        transcript_text = read_transcript_markdown(transcript_path)
        extracted_fields = extract_structured_fields(
            transcript_text,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            model=model,
        )
        structured_data.append(
            {
                "reunion": transcript_path.stem,
                "dolores": extracted_fields["dolores"],
            }
        )

    return structured_data


def main() -> int:
    """Run the structured extraction CLI."""
    parser = argparse.ArgumentParser(
        description="Extract structured data from cleaned meeting transcripts."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(DEFAULT_TRANSCRIPTS_DIR),
        help="Directory containing cleaned transcript markdown files.",
    )
    args = parser.parse_args()

    try:
        structured_data = extract_structured_data(args.input_dir)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(structured_data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
