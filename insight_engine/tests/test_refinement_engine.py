"""Tests for the iterative insight refinement loop."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from insight_engine import refinement_engine


def _mock_chat_response(payload: dict[str, object]) -> MagicMock:
    return MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=json.dumps(payload, ensure_ascii=False),
                )
            )
        ]
    )


class RefinementEngineTests(unittest.TestCase):
    def _build_dataframe(self):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "Categoria": "Operational efficiency and commercial strategy",
                    "Dolores": "Trabajo manual en reportes semanales",
                    "ideas": "Automatizar consolidación de reportes",
                    "kpi_medicion": "Horas dedicadas al reporte",
                    "Fuentes": "Excel\nERP",
                    "Tiempo_estimado": "4 a 6 semanas",
                    "Comentario": "Mantener foco en cierre comercial",
                },
                {
                    "Categoria": "Operational efficiency and commercial strategy",
                    "Dolores": "Proceso manual para consolidar reportes semanales",
                    "ideas": "Unificar información comercial",
                    "kpi_medicion": "Tiempo de cierre del reporte",
                    "Fuentes": "Excel\nERP",
                    "Tiempo_estimado": "4 a 6 semanas",
                    "Comentario": "",
                },
            ]
        )

    def test_refine_insight_dataframe_returns_best_scoring_version(self) -> None:
        client_mock = MagicMock()
        client_mock.chat.completions.create.side_effect = [
            _mock_chat_response(
                {
                    "score": 60,
                    "improvement_needed": True,
                    "summary": "Hay duplicados semánticos y una oportunidad de consolidación.",
                    "merge_candidates": [
                        {
                            "candidate_id": "merge-1",
                            "row_ids": ["row-1", "row-2"],
                            "confidence": "high",
                            "reason": "Ambas filas describen el mismo dolor de reportes manuales desde ángulos distintos.",
                            "consolidated_pain": "La consolidación de reportes semanales sigue siendo manual y consume tiempo clave del equipo comercial.",
                        }
                    ],
                    "issues": [
                        {
                            "issue_type": "semantic_duplicate",
                            "severity": "high",
                            "row_ids": ["row-1", "row-2"],
                            "recommended_action": "merge",
                            "details": "Las dos filas describen el mismo dolor con KPIs complementarios.",
                        }
                    ],
                }
            ),
            _mock_chat_response(
                {
                    "rows": [
                        {
                            "Categoria": "Operational efficiency and commercial strategy",
                            "Dolores": "La consolidación de reportes semanales sigue siendo manual y consume tiempo clave del equipo comercial.",
                            "ideas": "Automatizar la consolidación de reportes semanales y centralizar la información comercial en una sola vista.",
                            "kpi_medicion": "Horas dedicadas al reporte\nTiempo de cierre del reporte",
                            "Fuentes": "Excel\nERP",
                            "Tiempo_estimado": "4 a 6 semanas",
                            "Comentario": "Mantener foco en cierre comercial",
                        }
                    ],
                    "merge_decisions": [
                        {
                            "candidate_id": "merge-1",
                            "action": "merged",
                            "reason": "La información es complementaria y no se pierde nada al consolidarla.",
                        }
                    ],
                }
            ),
            _mock_chat_response(
                {
                    "score": 84,
                    "improvement_needed": True,
                    "summary": "La tabla está más consistente, pero aún puede precisarse la idea.",
                    "merge_candidates": [],
                    "issues": [
                        {
                            "issue_type": "idea_kpi_quality",
                            "severity": "low",
                            "row_ids": ["row-1"],
                            "recommended_action": "rewrite",
                            "details": "La idea podría ser un poco más concreta sin cambiar el fondo.",
                        }
                    ],
                }
            ),
            _mock_chat_response(
                {
                    "rows": [
                        {
                            "Categoria": "Operational efficiency and commercial strategy",
                            "Dolores": "La consolidación de reportes semanales sigue siendo manual y consume tiempo clave del equipo comercial.",
                            "ideas": "Automatizar reportes.",
                            "kpi_medicion": "Horas dedicadas al reporte\nTiempo de cierre del reporte",
                            "Fuentes": "Excel\nERP",
                            "Tiempo_estimado": "4 a 6 semanas",
                            "Comentario": "Mantener foco en cierre comercial",
                        }
                    ],
                    "merge_decisions": [],
                }
            ),
            _mock_chat_response(
                {
                    "score": 83,
                    "improvement_needed": True,
                    "summary": "La mejora adicional fue marginal.",
                    "merge_candidates": [],
                    "issues": [
                        {
                            "issue_type": "other",
                            "severity": "low",
                            "row_ids": ["row-1"],
                            "recommended_action": "keep",
                            "details": "La tabla ya está cerca de su mejor versión.",
                        }
                    ],
                }
            ),
        ]

        refined_dataframe = refinement_engine.refine_insight_dataframe(
            self._build_dataframe(),
            client=client_mock,
            system_prompt="Prompt de refinamiento",
            max_iterations=3,
            min_score_improvement=2,
        )

        self.assertEqual(1, len(refined_dataframe))
        self.assertIn("centralizar la información comercial", refined_dataframe.iloc[0]["ideas"])
        self.assertEqual("Mantener foco en cierre comercial", refined_dataframe.iloc[0]["Comentario"])

        metadata = refinement_engine.get_refinement_metadata(refined_dataframe)
        self.assertEqual([48, 84, 83], metadata["scores"])
        self.assertEqual(2, metadata["best_iteration"])
        self.assertEqual(84, metadata["best_score"])
        self.assertEqual("minimal_improvement", metadata["stopped_reason"])
        self.assertEqual(5, client_mock.chat.completions.create.call_count)
        self.assertEqual(60, metadata["iterations"][0]["model_score"])
        self.assertEqual(1, metadata["iterations"][0]["merge_candidate_count"])

    def test_refine_insight_dataframe_skips_refiner_when_no_improvement_is_needed(self) -> None:
        client_mock = MagicMock()
        client_mock.chat.completions.create.side_effect = [
            _mock_chat_response(
                {
                    "score": 91,
                    "improvement_needed": False,
                    "summary": "La tabla ya está suficientemente limpia y consistente.",
                    "merge_candidates": [],
                    "issues": [],
                }
            )
        ]

        refined_dataframe = refinement_engine.refine_insight_dataframe(
            self._build_dataframe().iloc[[0]].reset_index(drop=True),
            client=client_mock,
            system_prompt="Prompt de refinamiento",
        )

        self.assertEqual(1, len(refined_dataframe))
        self.assertEqual(
            "Trabajo manual en reportes semanales",
            refined_dataframe.iloc[0]["Dolores"],
        )

        metadata = refinement_engine.get_refinement_metadata(refined_dataframe)
        self.assertEqual([91], metadata["scores"])
        self.assertEqual(1, metadata["best_iteration"])
        self.assertEqual(91, metadata["best_score"])
        self.assertEqual("verifier_satisfied", metadata["stopped_reason"])
        self.assertEqual(1, client_mock.chat.completions.create.call_count)

    def test_evaluate_insight_dataframe_returns_merge_candidates_and_penalized_score(self) -> None:
        client_mock = MagicMock()
        client_mock.chat.completions.create.side_effect = [
            _mock_chat_response(
                {
                    "score": 90,
                    "improvement_needed": False,
                    "summary": "Hay una duplicación semántica clara.",
                    "merge_candidates": [
                        {
                            "candidate_id": "merge-13-14",
                            "row_ids": ["row-1", "row-2"],
                            "confidence": "high",
                            "reason": "Las filas comparten el mismo dolor de visibilidad insuficiente para planificar siembra.",
                            "consolidated_pain": "Existe visibilidad insuficiente y poco accionable para planificar la superficie plantada y decidir qué sembrar.",
                        }
                    ],
                    "issues": [
                        {
                            "issue_type": "merge_candidate",
                            "severity": "high",
                            "row_ids": ["row-1", "row-2"],
                            "recommended_action": "merge",
                            "details": "Se deben consolidar en una sola fila más representativa.",
                        }
                    ],
                }
            )
        ]

        verification = refinement_engine.evaluate_insight_dataframe(
            self._build_dataframe(),
            client=client_mock,
            system_prompt="Prompt de refinamiento",
        )

        self.assertEqual(90, verification.model_score)
        self.assertEqual(78, verification.score)
        self.assertTrue(verification.improvement_needed)
        self.assertEqual(["row-1", "row-2"], verification.merge_candidates[0]["row_ids"])
        self.assertEqual("high", verification.merge_candidates[0]["confidence"])

    def test_build_possible_merge_hints_flags_csv_rows_13_and_14(self) -> None:
        import pandas as pd

        csv_path = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "private"
            / "Dolores e ideas - Sheet1.csv"
        )
        dataframe = pd.read_csv(csv_path).iloc[[12, 13]].reset_index(drop=True)

        normalized_dataframe = refinement_engine._normalize_dataframe(dataframe)
        merge_hints = refinement_engine._build_possible_merge_hints(normalized_dataframe)

        self.assertEqual(1, len(merge_hints))
        self.assertEqual(["row-1", "row-2"], merge_hints[0]["row_ids"])
        self.assertIn("plant", merge_hints[0]["shared_keywords"])
        self.assertIn("planific", merge_hints[0]["shared_keywords"])


if __name__ == "__main__":
    unittest.main()
