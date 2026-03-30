"""Build actionable insight tables from structured meeting extraction output."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Sequence

from common.config import get_env
from common.llm_clients import create_openai_client
from insight_engine.data_extraction import DEFAULT_TRANSCRIPTS_DIR, extract_structured_data
from insight_engine.refinement_engine import get_refinement_metadata, refine_insight_dataframe


if TYPE_CHECKING:
    import pandas as pd


DEFAULT_INSIGHT_MODEL = "gpt-5.4-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_BATCH_SIZE = 64
DEFAULT_ENRICHMENT_BATCH_SIZE = 10
DEFAULT_SIMILARITY_THRESHOLD = 0.88
DEFAULT_WORKSHEET_NAME = "Sheet1"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INSIGHT_CATEGORY_OPTIONS_PATH = "insight_engine/docs/private/insight_category_options.txt"
DEFAULT_INSIGHT_SYSTEM_PROMPT_PATH = "insight_engine/docs/private/insight_system_prompt.txt"
DEFAULT_INSIGHT_TASK_PROMPT_PATH = "insight_engine/docs/private/insight_task_prompt.txt"
OUTPUT_COLUMNS = [
    "Categoria",
    "Dolores",
    "ideas",
    "kpi_medicion",
    "Fuentes",
    "Tiempo_estimado",
]
INSIGHT_CATEGORY_OPTIONS = (
    get_env(
        "INSIGHT_CATEGORY_OPTIONS",
        default=DEFAULT_INSIGHT_CATEGORY_OPTIONS_PATH,
    )
    or DEFAULT_INSIGHT_CATEGORY_OPTIONS_PATH
)
INSIGHT_SYSTEM_PROMPT = (
    get_env(
        "INSIGHT_SYSTEM_PROMPT",
        default=DEFAULT_INSIGHT_SYSTEM_PROMPT_PATH,
    )
    or DEFAULT_INSIGHT_SYSTEM_PROMPT_PATH
)
INSIGHT_TASK_PROMPT = (
    get_env(
        "INSIGHT_TASK_PROMPT",
        default=DEFAULT_INSIGHT_TASK_PROMPT_PATH,
    )
    or DEFAULT_INSIGHT_TASK_PROMPT_PATH
)
INSIGHT_ENGINE_COMPANY_CONTEXT = get_env("INSIGHT_ENGINE_COMPANY_CONTEXT", default="") or ""


def get_insight_model() -> str:
    """Return the configured model for insight generation."""
    return get_env("OPENAI_MODEL_INSIGHT_ENGINE", default=DEFAULT_INSIGHT_MODEL) or DEFAULT_INSIGHT_MODEL


def get_embedding_model() -> str:
    """Return the configured embedding model for semantic deduplication."""
    return get_env("OPENAI_EMBEDDING_MODEL", default=DEFAULT_EMBEDDING_MODEL) or DEFAULT_EMBEDDING_MODEL


def _read_text_or_file(
    configured_value: str,
    *,
    setting_name: str,
    required: bool = False,
) -> str:
    """Return inline text or the contents of a local text file."""
    configured_value = configured_value.strip()
    if not configured_value:
        if required:
            raise RuntimeError(f"Missing required configuration: {setting_name}")
        return ""

    candidate_path = Path(configured_value).expanduser()
    if not candidate_path.is_absolute():
        candidate_path = REPO_ROOT / candidate_path

    if candidate_path.is_file():
        try:
            return candidate_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"Failed to read {setting_name}: {exc}") from exc

    return configured_value


def get_company_context() -> str:
    """Return optional confidential business context for enrichment."""
    return _read_text_or_file(
        INSIGHT_ENGINE_COMPANY_CONTEXT,
        setting_name="INSIGHT_ENGINE_COMPANY_CONTEXT",
    )


def get_insight_category_options() -> list[str]:
    """Return the allowed categories for the insight table."""
    raw_value = _read_text_or_file(
        INSIGHT_CATEGORY_OPTIONS,
        setting_name="INSIGHT_CATEGORY_OPTIONS",
        required=True,
    )

    try:
        parsed_value = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed_value = None

    if isinstance(parsed_value, list):
        options = [str(item).strip() for item in parsed_value if str(item).strip()]
    else:
        options = [line.strip() for line in raw_value.splitlines() if line.strip()]

    if not options:
        raise RuntimeError("INSIGHT_CATEGORY_OPTIONS must define at least one category.")

    return options


def get_insight_system_prompt() -> str:
    """Return the system prompt used for insight enrichment."""
    return _read_text_or_file(
        INSIGHT_SYSTEM_PROMPT,
        setting_name="INSIGHT_SYSTEM_PROMPT",
        required=True,
    )


def get_insight_task_prompt() -> str:
    """Return the task prompt used for insight enrichment."""
    return _read_text_or_file(
        INSIGHT_TASK_PROMPT,
        setting_name="INSIGHT_TASK_PROMPT",
        required=True,
    )


def _load_pandas():
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "pandas is required for the insight engine. Install project dependencies first."
        ) from exc
    return pd


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_pain_point(value: str) -> str:
    """Normalize pain point text for exact deduplication."""
    return _normalize_whitespace(value).strip(" .,:;!-").casefold()


def extract_pain_point_candidates(
    structured_data: Sequence[dict[str, object]],
) -> list[dict[str, Any]]:
    """Flatten pain points from meeting-level structured extraction output."""
    candidates: list[dict[str, Any]] = []

    for entry in structured_data:
        if not isinstance(entry, dict):
            continue

        meeting_name = _normalize_whitespace(str(entry.get("reunion", "")).strip())
        pains = entry.get("dolores", [])
        if not isinstance(pains, list):
            continue

        for raw_pain in pains:
            pain_text = _normalize_whitespace(str(raw_pain).strip())
            if not pain_text:
                continue

            candidates.append(
                {
                    "meeting": meeting_name,
                    "pain": pain_text,
                    "normalized_pain": normalize_pain_point(pain_text),
                }
            )

    return candidates


def _deduplicate_exact_candidates(
    candidates: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collapse exact duplicates while keeping source traceability."""
    grouped: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        normalized = str(candidate["normalized_pain"])
        existing = grouped.get(normalized)
        if existing is None:
            grouped[normalized] = {
                "pain": str(candidate["pain"]),
                "normalized_pain": normalized,
                "source_pains": [str(candidate["pain"])],
                "source_meetings": [str(candidate["meeting"])] if str(candidate["meeting"]) else [],
            }
            continue

        existing["source_pains"].append(str(candidate["pain"]))
        if str(candidate["meeting"]):
            existing["source_meetings"].append(str(candidate["meeting"]))

    return list(grouped.values())


def _batched(values: Sequence[str], batch_size: int) -> Iterable[Sequence[str]]:
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def _get_embeddings(
    texts: Sequence[str],
    *,
    client: Any,
    model: str,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
) -> list[list[float]]:
    """Fetch embeddings in batches for the provided text collection."""
    embeddings: list[list[float]] = []

    for batch in _batched(list(texts), batch_size):
        response = client.embeddings.create(model=model, input=list(batch))
        embeddings.extend([list(item.embedding) for item in response.data])

    return embeddings


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def _average_embedding(vectors: Sequence[Sequence[float]]) -> list[float]:
    if not vectors:
        return []

    vector_length = len(vectors[0])
    sums = [0.0] * vector_length

    for vector in vectors:
        for index, value in enumerate(vector):
            sums[index] += value

    return [value / len(vectors) for value in sums]


def deduplicate_pain_points(
    structured_data: Sequence[dict[str, object]],
    *,
    client: Any | None = None,
    embedding_model: str | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """Group semantically similar pain points while preserving source traceability."""
    candidates = extract_pain_point_candidates(structured_data)
    if not candidates:
        return []

    unique_candidates = _deduplicate_exact_candidates(candidates)
    if len(unique_candidates) == 1:
        only_candidate = unique_candidates[0]
        return [
            {
                "group_id": "pain-group-1",
                "representative_pain": only_candidate["pain"],
                "source_pains": list(dict.fromkeys(only_candidate["source_pains"])),
                "source_meetings": list(dict.fromkeys(only_candidate["source_meetings"])),
            }
        ]

    resolved_client = client or create_openai_client()
    resolved_model = embedding_model or get_embedding_model()
    embeddings = _get_embeddings(
        [str(candidate["pain"]) for candidate in unique_candidates],
        client=resolved_client,
        model=resolved_model,
    )

    clusters: list[dict[str, Any]] = []
    for candidate, embedding in zip(unique_candidates, embeddings):
        best_match_index = -1
        best_similarity = -1.0

        for index, cluster in enumerate(clusters):
            similarity = _cosine_similarity(embedding, cluster["centroid"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_index = index

        if best_match_index >= 0 and best_similarity >= similarity_threshold:
            cluster = clusters[best_match_index]
            cluster["members"].append(candidate)
            cluster["embeddings"].append(embedding)
            cluster["centroid"] = _average_embedding(cluster["embeddings"])
            continue

        clusters.append(
            {
                "members": [candidate],
                "embeddings": [embedding],
                "centroid": list(embedding),
            }
        )

    deduplicated_clusters: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters, start=1):
        members = cluster["members"]
        representative = min(
            members,
            key=lambda item: (len(str(item["pain"])), str(item["pain"]).casefold()),
        )

        source_pains: list[str] = []
        source_meetings: list[str] = []
        for member in members:
            source_pains.extend(str(value) for value in member["source_pains"])
            source_meetings.extend(str(value) for value in member["source_meetings"])

        deduplicated_clusters.append(
            {
                "group_id": f"pain-group-{index}",
                "representative_pain": str(representative["pain"]),
                "source_pains": list(dict.fromkeys(source_pains)),
                "source_meetings": list(dict.fromkeys(source_meetings)),
            }
        )

    return deduplicated_clusters


def _strip_json_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return cleaned


def _enrichment_response_schema() -> dict[str, Any]:
    insight_category_options = get_insight_category_options()

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "insight_rows",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "group_id": {"type": "string"},
                                "Categoria": {"type": "string", "enum": insight_category_options},
                                "Dolores": {"type": "string"},
                                "ideas": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "maxItems": 2,
                                },
                                "kpi_medicion": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "Fuentes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "Tiempo_estimado": {"type": "string"},
                            },
                            "required": [
                                "group_id",
                                "Categoria",
                                "Dolores",
                                "ideas",
                                "kpi_medicion",
                                "Fuentes",
                                "Tiempo_estimado",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["rows"],
                "additionalProperties": False,
            },
        },
    }


def _format_cell(value: str | Sequence[str]) -> str:
    if isinstance(value, str):
        return _normalize_whitespace(value)
    return "\n".join(_normalize_whitespace(str(item)) for item in value if str(item).strip())


def _validate_enriched_row(row: dict[str, Any]) -> dict[str, str]:
    insight_category_options = get_insight_category_options()
    category = _normalize_whitespace(str(row.get("Categoria", "")).strip())
    if category not in insight_category_options:
        raise RuntimeError(f"Unexpected category returned by the model: {category}")

    ideas = [str(item).strip() for item in row.get("ideas", []) if str(item).strip()]
    if len(ideas) > 2:
        raise RuntimeError("The enrichment model returned more than 2 ideas for a pain point.")

    kpis = [str(item).strip() for item in row.get("kpi_medicion", []) if str(item).strip()]
    sources = [str(item).strip() for item in row.get("Fuentes", []) if str(item).strip()]
    pain = _normalize_whitespace(str(row.get("Dolores", "")).strip())
    estimated_time = _normalize_whitespace(str(row.get("Tiempo_estimado", "")).strip())

    if not pain:
        raise RuntimeError("The enrichment model returned an empty consolidated pain point.")
    if not estimated_time:
        raise RuntimeError("The enrichment model returned an empty estimated time.")

    return {
        "Categoria": category,
        "Dolores": pain,
        "ideas": _format_cell(ideas),
        "kpi_medicion": _format_cell(kpis),
        "Fuentes": _format_cell(sources),
        "Tiempo_estimado": estimated_time,
    }


def enrich_pain_point_clusters(
    pain_point_clusters: Sequence[dict[str, Any]],
    *,
    client: Any | None = None,
    model: str | None = None,
    company_context: str | None = None,
    batch_size: int = DEFAULT_ENRICHMENT_BATCH_SIZE,
) -> list[dict[str, str]]:
    """Enrich semantically deduplicated pain-point clusters with structured insight rows."""
    if not pain_point_clusters:
        return []

    resolved_client = client or create_openai_client()
    resolved_model = model or get_insight_model()
    resolved_company_context = company_context if company_context is not None else get_company_context()
    insight_category_options = get_insight_category_options()
    insight_system_prompt = get_insight_system_prompt()
    insight_task_prompt = get_insight_task_prompt()

    rows_by_group_id: dict[str, dict[str, str]] = {}

    for batch in _batched(list(pain_point_clusters), batch_size):
        user_payload = {
            "allowed_categories": insight_category_options,
            "company_context": resolved_company_context,
            "pain_point_groups": [
                {
                    "group_id": cluster["group_id"],
                    "representative_pain": cluster["representative_pain"],
                    "source_pains": cluster["source_pains"],
                    "source_meetings": cluster["source_meetings"],
                }
                for cluster in batch
            ],
        }

        try:
            response = resolved_client.chat.completions.create(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": insight_system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"{insight_task_prompt}\n\n"
                            f"Input JSON:\n{json.dumps(user_payload, ensure_ascii=False)}"
                        ),
                    },
                ],
                response_format=_enrichment_response_schema(),
                temperature=0.2,
            )
        except Exception as exc:
            raise RuntimeError(f"Insight enrichment failed: {exc}") from exc

        message_content = response.choices[0].message.content or ""

        try:
            parsed_payload = json.loads(_strip_json_fence(message_content))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse insight enrichment output: {exc}") from exc

        model_rows = parsed_payload.get("rows", [])
        if not isinstance(model_rows, list):
            raise RuntimeError("Insight enrichment output must contain a rows list.")

        expected_group_ids = {str(cluster["group_id"]) for cluster in batch}
        returned_group_ids = {str(row.get("group_id", "")) for row in model_rows}
        if returned_group_ids != expected_group_ids:
            raise RuntimeError(
                "Insight enrichment output does not match the expected pain point groups."
            )

        for row in model_rows:
            rows_by_group_id[str(row["group_id"])] = _validate_enriched_row(row)

    return [rows_by_group_id[str(cluster["group_id"])] for cluster in pain_point_clusters]


def build_insight_dataframe(
    structured_data: Sequence[dict[str, object]],
    *,
    client: Any | None = None,
    embedding_model: str | None = None,
    insight_model: str | None = None,
    company_context: str | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> "pd.DataFrame":
    """Build the final insight dataframe expected by downstream export steps."""
    pd = _load_pandas()

    clusters = deduplicate_pain_points(
        structured_data,
        client=client,
        embedding_model=embedding_model,
        similarity_threshold=similarity_threshold,
    )
    rows = enrich_pain_point_clusters(
        clusters,
        client=client,
        model=insight_model,
        company_context=company_context,
    )

    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def build_refined_insight_dataframe(
    structured_data: Sequence[dict[str, object]],
    *,
    client: Any | None = None,
    embedding_model: str | None = None,
    insight_model: str | None = None,
    company_context: str | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> "pd.DataFrame":
    """Build and refine the insight dataframe expected by downstream export steps."""
    dataframe = build_insight_dataframe(
        structured_data,
        client=client,
        embedding_model=embedding_model,
        insight_model=insight_model,
        company_context=company_context,
        similarity_threshold=similarity_threshold,
    )
    return refine_insight_dataframe(dataframe)


def load_structured_data(input_path: str | Path) -> list[dict[str, object]]:
    """Load structured data either from a JSON file or by extracting it from transcripts."""
    resolved_path = Path(input_path)

    if resolved_path.is_file():
        try:
            payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RuntimeError(f"Failed to read structured data file: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse structured data JSON: {exc}") from exc

        if not isinstance(payload, list):
            raise RuntimeError("Structured data JSON must contain a list.")

        return [entry for entry in payload if isinstance(entry, dict)]

    return extract_structured_data(resolved_path)


def main() -> int:
    """Run the insight engine CLI."""
    parser = argparse.ArgumentParser(
        description="Build an actionable insight dataframe from meeting transcripts or structured JSON."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=str(DEFAULT_TRANSCRIPTS_DIR),
        help="Transcript directory or JSON file produced by insight_engine.data_extraction.",
    )
    parser.add_argument(
        "--export-google-sheet",
        action="store_true",
        help="Export the resulting dataframe to Google Sheets.",
    )
    parser.add_argument(
        "--worksheet-name",
        default=DEFAULT_WORKSHEET_NAME,
        help="Worksheet name to use when exporting to Google Sheets.",
    )
    args = parser.parse_args()

    try:
        structured_data = load_structured_data(args.input_path)
        refined_dataframe = build_refined_insight_dataframe(structured_data)
        print("Dataframe was generated successfully.")

        refinement_metadata = get_refinement_metadata(refined_dataframe)
        if refinement_metadata.get("scores"):
            scores = " -> ".join(str(score) for score in refinement_metadata["scores"])
            print(
                "Refinement completed successfully "
                f"(scores: {scores}, best: {refinement_metadata['best_score']})."
            )

        if args.export_google_sheet:
            from insight_engine.export_data_to_google_sheet import export_dataframe_to_google_sheet

            export_summary = export_dataframe_to_google_sheet(
                refined_dataframe,
                worksheet_name=args.worksheet_name,
            )
            print(export_summary)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
