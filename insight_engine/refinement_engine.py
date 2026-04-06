"""Iterative refinement helpers for generated insight tables."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from common.config import get_env, read_text_or_file
from common.llm_clients import create_openai_client


if TYPE_CHECKING:
    import pandas as pd


DEFAULT_REFINEMENT_MODEL = "gpt-5.4-mini"
DEFAULT_REFINEMENT_SYSTEM_PROMPT_PATH = "insight_engine/docs/private/insight_refinement_system_prompt.txt"
DEFAULT_INSIGHT_CATEGORY_OPTIONS_PATH = "insight_engine/docs/private/insight_category_options.txt"
DEFAULT_MAX_ITERATIONS = 3
DEFAULT_MIN_SCORE_IMPROVEMENT = 2
REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_COLUMNS = [
    "Categoria",
    "Dolores",
    "ideas",
    "kpi_medicion",
    "Fuentes",
    "Tiempo_estimado",
]
SPANISH_STOPWORDS = {
    "ante",
    "bajo",
    "como",
    "con",
    "cuando",
    "donde",
    "desde",
    "entre",
    "esta",
    "este",
    "estos",
    "estas",
    "hacia",
    "hasta",
    "para",
    "pero",
    "poca",
    "poco",
    "porque",
    "por",
    "que",
    "qué",
    "sobre",
    "solo",
    "tipo",
    "una",
    "uno",
    "unos",
    "unas",
    "del",
    "las",
    "los",
    "hay",
    "sin",
    "más",
    "mas",
}
REFINEMENT_SYSTEM_PROMPT = (
    get_env(
        "REFINEMENT_SYSTEM_PROMPT",
        default=DEFAULT_REFINEMENT_SYSTEM_PROMPT_PATH,
    )
    or DEFAULT_REFINEMENT_SYSTEM_PROMPT_PATH
)
INSIGHT_CATEGORY_OPTIONS = (
    get_env(
        "INSIGHT_CATEGORY_OPTIONS",
        default=DEFAULT_INSIGHT_CATEGORY_OPTIONS_PATH,
    )
    or DEFAULT_INSIGHT_CATEGORY_OPTIONS_PATH
)


@dataclass(frozen=True)
class VerificationResult:
    model_score: int
    score: int
    improvement_needed: bool
    summary: str
    merge_candidates: list[dict[str, Any]]
    issues: list[dict[str, Any]]


@dataclass(frozen=True)
class RefinementRunResult:
    dataframe: "pd.DataFrame"
    metadata: dict[str, Any]


def _load_pandas():
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "pandas is required for insight refinement. Install project dependencies first."
        ) from exc
    return pd


def _read_text_or_file(configured_value: str, *, setting_name: str, required: bool = False) -> str:
    return read_text_or_file(configured_value, setting_name=setting_name, repo_root=REPO_ROOT, required=required)


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _normalize_cell_value(value: object) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    normalized_lines = [_normalize_whitespace(line) for line in text.split("\n")]
    return "\n".join(line for line in normalized_lines if line)


def _strip_json_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return cleaned


def get_refinement_model() -> str:
    """Return the configured model for the refinement loop."""
    return get_env("OPENAI_MODEL_INSIGHT_ENGINE", default=DEFAULT_REFINEMENT_MODEL) or DEFAULT_REFINEMENT_MODEL


def get_refinement_system_prompt() -> str:
    """Return the system prompt shared by verifier and refiner."""
    return _read_text_or_file(
        REFINEMENT_SYSTEM_PROMPT,
        setting_name="REFINEMENT_SYSTEM_PROMPT",
        required=True,
    )


def get_insight_category_options() -> list[str]:
    """Return the configured category list when available."""
    raw_value = _read_text_or_file(
        INSIGHT_CATEGORY_OPTIONS,
        setting_name="INSIGHT_CATEGORY_OPTIONS",
        required=False,
    )

    if not raw_value:
        return []

    try:
        parsed_value = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed_value = None

    if isinstance(parsed_value, list):
        options = [str(item).strip() for item in parsed_value if str(item).strip()]
    else:
        options = [line.strip() for line in raw_value.splitlines() if line.strip()]

    return options


def _ensure_required_columns(dataframe: "pd.DataFrame") -> None:
    missing_columns = [column for column in CORE_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(
            "The insight dataframe is missing required columns: "
            + ", ".join(missing_columns)
        )


def _normalize_dataframe(dataframe: "pd.DataFrame") -> "pd.DataFrame":
    pd = _load_pandas()
    _ensure_required_columns(dataframe)

    resolved_columns = [str(column) for column in dataframe.columns]
    if len(resolved_columns) != len(set(resolved_columns)):
        raise ValueError("The insight dataframe contains duplicate column names after string normalization.")

    normalized_rows: list[dict[str, str]] = []
    for row in dataframe.fillna("").to_dict(orient="records"):
        normalized_rows.append(
            {
                str(column): _normalize_cell_value(row[column])
                for column in dataframe.columns
            }
        )

    normalized_dataframe = pd.DataFrame(normalized_rows, columns=resolved_columns)
    normalized_dataframe.attrs = dict(dataframe.attrs)
    return normalized_dataframe


def _serialize_dataframe(dataframe: "pd.DataFrame") -> list[dict[str, Any]]:
    records = dataframe.to_dict(orient="records")
    return [
        {
            "row_id": f"row-{index}",
            "values": {column: _normalize_cell_value(value) for column, value in record.items()},
        }
        for index, record in enumerate(records, start=1)
    ]


def _normalize_domain_token(token: str) -> str:
    token = token.casefold()

    if token.startswith("plant") or token.startswith("siembr"):
        return "plant"
    if token.startswith("planific"):
        return "planific"
    if token.startswith("cultiv"):
        return "cultiv"
    if token.startswith("visibil"):
        return "visibil"
    if token.startswith("registro") or token.startswith("inventari"):
        return "registro"
    if token.startswith("proyec") or token.startswith("escenar"):
        return "proyec"
    if token.startswith("rentab"):
        return "rentab"

    return token


def _extract_row_keywords(row_values: dict[str, str]) -> set[str]:
    text = "\n".join(
        [
            row_values.get("Categoria", ""),
            row_values.get("Dolores", ""),
            row_values.get("ideas", ""),
            row_values.get("kpi_medicion", ""),
        ]
    )
    raw_tokens = re.findall(r"[a-záéíóúñü]+", text.casefold())

    keywords: set[str] = set()
    for raw_token in raw_tokens:
        normalized_token = _normalize_domain_token(raw_token)
        if len(normalized_token) < 5 or normalized_token in SPANISH_STOPWORDS:
            continue
        keywords.add(normalized_token)

    return keywords


def _build_possible_merge_hints(dataframe: "pd.DataFrame") -> list[dict[str, Any]]:
    serialized_rows = _serialize_dataframe(dataframe)
    indexed_rows = [
        {
            "row_id": row["row_id"],
            "values": row["values"],
            "category": row["values"].get("Categoria", ""),
            "keywords": _extract_row_keywords(row["values"]),
        }
        for row in serialized_rows
    ]

    hints: list[dict[str, Any]] = []
    for left_index, left_row in enumerate(indexed_rows):
        for right_row in indexed_rows[left_index + 1 :]:
            if left_row["category"] != right_row["category"]:
                continue

            shared_keywords = sorted(left_row["keywords"] & right_row["keywords"])
            if len(shared_keywords) < 2:
                continue

            hints.append(
                {
                    "row_ids": [left_row["row_id"], right_row["row_id"]],
                    "shared_keywords": shared_keywords[:6],
                    "reason": (
                        "Same category and shared planning vocabulary: "
                        + ", ".join(shared_keywords[:4])
                    ),
                }
            )

    hints.sort(
        key=lambda item: (
            -len(item["shared_keywords"]),
            item["row_ids"],
        )
    )
    return hints[:20]


def _verification_response_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "insight_table_verification",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "improvement_needed": {"type": "boolean"},
                    "summary": {"type": "string"},
                    "merge_candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "candidate_id": {"type": "string"},
                                "row_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "confidence": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                },
                                "reason": {"type": "string"},
                                "consolidated_pain": {"type": "string"},
                            },
                            "required": [
                                "candidate_id",
                                "row_ids",
                                "confidence",
                                "reason",
                                "consolidated_pain",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "issue_type": {
                                    "type": "string",
                                    "enum": [
                                        "semantic_duplicate",
                                        "merge_candidate",
                                        "weak_row",
                                        "redundant_row",
                                        "category_alignment",
                                        "idea_kpi_quality",
                                        "other",
                                    ],
                                },
                                "severity": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                },
                                "row_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "recommended_action": {
                                    "type": "string",
                                    "enum": ["keep", "merge", "rewrite", "drop", "review"],
                                },
                                "details": {"type": "string"},
                            },
                            "required": [
                                "issue_type",
                                "severity",
                                "row_ids",
                                "recommended_action",
                                "details",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "score",
                    "improvement_needed",
                    "summary",
                    "merge_candidates",
                    "issues",
                ],
                "additionalProperties": False,
            },
        },
    }


def _refiner_response_schema(columns: list[str], *, max_rows: int) -> dict[str, Any]:
    row_properties = {column: {"type": "string"} for column in columns}

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "refined_insight_table",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "maxItems": max_rows,
                        "items": {
                            "type": "object",
                            "properties": row_properties,
                            "required": list(columns),
                            "additionalProperties": False,
                        },
                    },
                    "merge_decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "candidate_id": {"type": "string"},
                                "action": {
                                    "type": "string",
                                    "enum": ["merged", "kept_separate"],
                                },
                                "reason": {"type": "string"},
                            },
                            "required": ["candidate_id", "action", "reason"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["rows", "merge_decisions"],
                "additionalProperties": False,
            },
        },
    }


def _semantic_duplicate_penalty(merge_candidates: list[dict[str, Any]]) -> int:
    weights = {
        "high": 12,
        "medium": 6,
        "low": 0,
    }
    return min(30, sum(weights.get(str(candidate.get("confidence", "")), 0) for candidate in merge_candidates))


def _parse_json_response(content: str, *, error_prefix: str) -> dict[str, Any]:
    try:
        payload = json.loads(_strip_json_fence(content))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{error_prefix}: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"{error_prefix}: model output must be a JSON object.")

    return payload


def evaluate_insight_dataframe(
    dataframe: "pd.DataFrame",
    *,
    client: Any | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
) -> VerificationResult:
    """Score the current table and identify structured issues for refinement."""
    normalized_dataframe = _normalize_dataframe(dataframe)
    resolved_client = client or create_openai_client()
    resolved_model = model or get_refinement_model()
    resolved_system_prompt = system_prompt or get_refinement_system_prompt()

    payload = {
        "columns": normalized_dataframe.columns.tolist(),
        "core_columns": CORE_COLUMNS,
        "allowed_categories": get_insight_category_options(),
        "rows": _serialize_dataframe(normalized_dataframe),
        "possible_merge_hints": _build_possible_merge_hints(normalized_dataframe),
    }
    task_prompt = (
        "Task: verify the quality of this insight table.\n"
        "Score it from 0 to 100.\n"
        "Be practical and aggressive about semantic duplication.\n"
        "Rows that differ only in wording, angle, emphasis, upstream data gap, or downstream decision consequence "
        "must be treated as the same pain when they point to the same underlying business problem.\n"
        "This includes cases where one row describes missing trusted baseline data and another describes weak "
        "planning or projections for that same decision domain.\n"
        "Example: 'falta un registro confiable de cultivos plantados' and 'poca información accionable para decidir "
        "qué plantar' should be merged into one planning-visibility pain.\n"
        "Return explicit merge_candidates with row identifiers, confidence, reasons, and a suggested consolidated pain.\n"
        "Penalize unresolved semantic duplication heavily in the score.\n"
        "Prefer fewer, stronger, more representative rows over many slightly different rows.\n"
        "Evaluate semantic duplicates, weak or redundant rows, category alignment, idea/KPI quality, "
        "and business usefulness for margin, efficiency, and decision-making.\n"
        "Set improvement_needed to true only when another refinement pass would materially improve the table.\n"
        "Use possible_merge_hints as strong cues and err toward merging when the same underlying pain is being described.\n"
        "Use only the provided row_ids when referencing issues.\n"
        "Return JSON that matches the schema.\n\n"
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    try:
        response = resolved_client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": resolved_system_prompt},
                {"role": "user", "content": task_prompt},
            ],
            response_format=_verification_response_schema(),
            temperature=0.1,
        )
    except Exception as exc:
        raise RuntimeError(f"Insight verification failed: {exc}") from exc

    payload = _parse_json_response(
        response.choices[0].message.content or "",
        error_prefix="Failed to parse verifier output",
    )

    score = int(payload.get("score", 0))
    if score < 0 or score > 100:
        raise RuntimeError("Verifier score must be between 0 and 100.")

    merge_candidates_payload = payload.get("merge_candidates", [])
    if not isinstance(merge_candidates_payload, list):
        raise RuntimeError("Verifier output must contain a merge_candidates list.")

    merge_candidates: list[dict[str, Any]] = []
    for candidate in merge_candidates_payload:
        if not isinstance(candidate, dict):
            raise RuntimeError("Each merge candidate must be an object.")

        merge_candidates.append(
            {
                "candidate_id": str(candidate.get("candidate_id", "")).strip(),
                "row_ids": [
                    str(item).strip()
                    for item in candidate.get("row_ids", [])
                    if str(item).strip()
                ],
                "confidence": str(candidate.get("confidence", "")).strip(),
                "reason": _normalize_whitespace(str(candidate.get("reason", "")).strip()),
                "consolidated_pain": _normalize_whitespace(
                    str(candidate.get("consolidated_pain", "")).strip()
                ),
            }
        )

    issues_payload = payload.get("issues", [])
    if not isinstance(issues_payload, list):
        raise RuntimeError("Verifier output must contain an issues list.")

    issues: list[dict[str, Any]] = []
    for issue in issues_payload:
        if not isinstance(issue, dict):
            raise RuntimeError("Each verifier issue must be an object.")

        issues.append(
            {
                "issue_type": str(issue.get("issue_type", "")).strip(),
                "severity": str(issue.get("severity", "")).strip(),
                "row_ids": [
                    str(item).strip()
                    for item in issue.get("row_ids", [])
                    if str(item).strip()
                ],
                "recommended_action": str(issue.get("recommended_action", "")).strip(),
                "details": _normalize_whitespace(str(issue.get("details", "")).strip()),
            }
        )

    adjusted_score = max(0, score - _semantic_duplicate_penalty(merge_candidates))
    high_or_medium_merges = any(
        candidate["confidence"] in {"high", "medium"}
        for candidate in merge_candidates
    )

    return VerificationResult(
        model_score=score,
        score=adjusted_score,
        improvement_needed=bool(payload.get("improvement_needed", False) or high_or_medium_merges),
        summary=_normalize_whitespace(str(payload.get("summary", "")).strip()),
        merge_candidates=merge_candidates,
        issues=issues,
    )


def _build_refined_dataframe(
    rows: list[dict[str, Any]],
    *,
    columns: list[str],
    input_row_count: int,
) -> "pd.DataFrame":
    pd = _load_pandas()

    if input_row_count > 0 and not rows:
        raise RuntimeError("Refiner returned an empty table for a non-empty input.")
    if len(rows) > input_row_count:
        raise RuntimeError("Refiner returned more rows than the input table, which is not allowed.")

    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("Each refined row must be an object.")

        normalized_rows.append(
            {
                column: _normalize_cell_value(row.get(column, ""))
                for column in columns
            }
        )

    return pd.DataFrame(normalized_rows, columns=columns)


def _validate_merge_decisions(
    decisions: list[dict[str, Any]],
    *,
    verification: VerificationResult,
) -> None:
    required_candidate_ids = {
        candidate["candidate_id"]
        for candidate in verification.merge_candidates
        if candidate["confidence"] == "high"
    }
    if not required_candidate_ids:
        return

    decision_map = {
        str(decision.get("candidate_id", "")).strip(): decision
        for decision in decisions
        if str(decision.get("candidate_id", "")).strip()
    }
    missing_candidate_ids = sorted(required_candidate_ids - set(decision_map))
    if missing_candidate_ids:
        raise RuntimeError(
            "Refiner output is missing merge decisions for high-confidence candidates: "
            + ", ".join(missing_candidate_ids)
        )

    for candidate_id in required_candidate_ids:
        reason = _normalize_whitespace(str(decision_map[candidate_id].get("reason", "")).strip())
        if not reason:
            raise RuntimeError(
                f"Refiner output must explain the decision for high-confidence candidate {candidate_id}."
            )


def refine_dataframe_once(
    dataframe: "pd.DataFrame",
    verification: VerificationResult,
    *,
    client: Any | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
) -> "pd.DataFrame":
    """Apply one conservative refinement pass using structured verifier feedback."""
    normalized_dataframe = _normalize_dataframe(dataframe)
    resolved_client = client or create_openai_client()
    resolved_model = model or get_refinement_model()
    resolved_system_prompt = system_prompt or get_refinement_system_prompt()
    columns = normalized_dataframe.columns.tolist()

    payload = {
        "columns": columns,
        "core_columns": CORE_COLUMNS,
        "allowed_categories": get_insight_category_options(),
        "rows": _serialize_dataframe(normalized_dataframe),
        "verification": {
            "model_score": verification.model_score,
            "score": verification.score,
            "summary": verification.summary,
            "merge_candidates": verification.merge_candidates,
            "issues": verification.issues,
        },
    }
    task_prompt = (
        "Task: refine this insight table using the verifier feedback.\n"
        "Be conservative about information loss, but aggressive about semantic duplication.\n"
        "Rows that differ only in wording, angle, or emphasis must be merged when they describe the same business pain.\n"
        "Treat upstream missing-data rows and downstream weak-planning rows as one pain when they concern the same decision domain.\n"
        "Example: a row about missing crop registry data and another about weak planting decision scenarios should be consolidated into one planning-visibility pain.\n"
        "Apply every high-confidence merge candidate unless keeping rows separate is necessary to avoid losing important information.\n"
        "Rewrite only weak or inconsistent rows.\n"
        "Keep strong rows unchanged unless they are part of a merge.\n"
        "Preserve useful information and keep the same columns in every returned row.\n"
        "Do not invent new facts.\n"
        "Never increase the number of rows.\n"
        "Prefer fewer, stronger, more representative rows over many slightly different rows.\n"
        "Focus on deduplication, consistency, and business usefulness for margin, efficiency, and decision-making.\n"
        "Return merge_decisions for every high-confidence merge candidate.\n"
        "Return JSON that matches the schema.\n\n"
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    try:
        response = resolved_client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": resolved_system_prompt},
                {"role": "user", "content": task_prompt},
            ],
            response_format=_refiner_response_schema(
                columns,
                max_rows=len(normalized_dataframe),
            ),
            temperature=0.2,
        )
    except Exception as exc:
        raise RuntimeError(f"Insight refinement failed: {exc}") from exc

    payload = _parse_json_response(
        response.choices[0].message.content or "",
        error_prefix="Failed to parse refiner output",
    )

    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise RuntimeError("Refiner output must contain a rows list.")

    merge_decisions = payload.get("merge_decisions", [])
    if not isinstance(merge_decisions, list):
        raise RuntimeError("Refiner output must contain a merge_decisions list.")
    _validate_merge_decisions(merge_decisions, verification=verification)

    refined_dataframe = _build_refined_dataframe(
        rows,
        columns=columns,
        input_row_count=len(normalized_dataframe),
    )
    refined_dataframe.attrs = dict(dataframe.attrs)
    return refined_dataframe


def run_refinement_loop(
    dataframe: "pd.DataFrame",
    *,
    client: Any | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    min_score_improvement: int = DEFAULT_MIN_SCORE_IMPROVEMENT,
) -> RefinementRunResult:
    """Run verify -> refine up to a bounded number of iterations and keep the best version."""
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1.")

    current_dataframe = _normalize_dataframe(dataframe)
    if current_dataframe.empty:
        metadata = {
            "scores": [],
            "iterations": [],
            "best_iteration": 0,
            "best_score": 0,
            "stopped_reason": "empty_dataframe",
        }
        current_dataframe.attrs = dict(dataframe.attrs)
        current_dataframe.attrs["refinement_metadata"] = metadata
        return RefinementRunResult(dataframe=current_dataframe, metadata=metadata)

    best_dataframe = current_dataframe.copy()
    best_dataframe.attrs = dict(dataframe.attrs)
    best_score = -1
    best_iteration = 0
    iterations_metadata: list[dict[str, Any]] = []
    previous_score: int | None = None
    stopped_reason = "max_iterations_reached"

    for iteration in range(1, max_iterations + 1):
        verification = evaluate_insight_dataframe(
            current_dataframe,
            client=client,
            model=model,
            system_prompt=system_prompt,
        )
        score_delta = verification.score - previous_score if previous_score is not None else None

        iteration_metadata = {
            "iteration": iteration,
            "model_score": verification.model_score,
            "score": verification.score,
            "score_delta": score_delta,
            "improvement_needed": verification.improvement_needed,
            "summary": verification.summary,
            "merge_candidates": verification.merge_candidates,
            "merge_candidate_count": len(verification.merge_candidates),
            "issue_count": len(verification.issues),
            "issues": verification.issues,
            "row_count": len(current_dataframe),
        }
        iterations_metadata.append(iteration_metadata)

        if verification.score > best_score:
            best_dataframe = current_dataframe.copy()
            best_dataframe.attrs = dict(dataframe.attrs)
            best_score = verification.score
            best_iteration = iteration

        if not verification.improvement_needed:
            stopped_reason = "verifier_satisfied"
            break

        if not verification.issues:
            stopped_reason = "no_actionable_issues"
            break

        if score_delta is not None and score_delta < min_score_improvement:
            stopped_reason = "minimal_improvement"
            break

        if iteration == max_iterations:
            stopped_reason = "max_iterations_reached"
            break

        refined_candidate = refine_dataframe_once(
            current_dataframe,
            verification,
            client=client,
            model=model,
            system_prompt=system_prompt,
        )
        if refined_candidate.equals(current_dataframe):
            stopped_reason = "no_change"
            break

        current_dataframe = refined_candidate
        previous_score = verification.score

    metadata = {
        "scores": [item["score"] for item in iterations_metadata],
        "iterations": iterations_metadata,
        "best_iteration": best_iteration,
        "best_score": best_score if best_score >= 0 else 0,
        "stopped_reason": stopped_reason,
    }
    best_dataframe.attrs["refinement_metadata"] = metadata
    return RefinementRunResult(dataframe=best_dataframe, metadata=metadata)


def refine_insight_dataframe(
    dataframe: "pd.DataFrame",
    *,
    client: Any | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    min_score_improvement: int = DEFAULT_MIN_SCORE_IMPROVEMENT,
) -> "pd.DataFrame":
    """Return the best-scoring refined dataframe and attach metadata in dataframe attrs."""
    return run_refinement_loop(
        dataframe,
        client=client,
        model=model,
        system_prompt=system_prompt,
        max_iterations=max_iterations,
        min_score_improvement=min_score_improvement,
    ).dataframe


def get_refinement_metadata(dataframe: "pd.DataFrame") -> dict[str, Any]:
    """Return refinement metadata stored in dataframe attrs."""
    return dict(dataframe.attrs.get("refinement_metadata", {}))
