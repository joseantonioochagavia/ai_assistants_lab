"""Tests for the actionable insight engine pipeline."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from insight_engine import export_data_to_google_sheet, insight_engine


class DeduplicationTests(unittest.TestCase):
    def test_extract_pain_point_candidates_flattens_structured_input(self) -> None:
        candidates = insight_engine.extract_pain_point_candidates(
            [
                {
                    "reunion": "Meeting A",
                    "dolores": ["  Falta de visibilidad comercial  ", "", "Trabajo manual"],
                },
                {
                    "reunion": "Meeting B",
                    "dolores": ["Trabajo manual"],
                },
            ]
        )

        self.assertEqual(
            [
                {
                    "meeting": "Meeting A",
                    "pain": "Falta de visibilidad comercial",
                    "normalized_pain": "falta de visibilidad comercial",
                },
                {
                    "meeting": "Meeting A",
                    "pain": "Trabajo manual",
                    "normalized_pain": "trabajo manual",
                },
                {
                    "meeting": "Meeting B",
                    "pain": "Trabajo manual",
                    "normalized_pain": "trabajo manual",
                },
            ],
            candidates,
        )

    def test_deduplicate_pain_points_groups_exact_and_semantic_duplicates(self) -> None:
        client_mock = MagicMock()
        client_mock.embeddings.create.return_value = MagicMock(
            data=[
                MagicMock(embedding=[1.0, 0.0]),
                MagicMock(embedding=[0.0, 1.0]),
                MagicMock(embedding=[0.99, 0.01]),
            ]
        )

        clusters = insight_engine.deduplicate_pain_points(
            [
                {"reunion": "Meeting A", "dolores": ["Trabajo manual en reportes", "Falta de trazabilidad"]},
                {"reunion": "Meeting B", "dolores": ["Trabajo manual para reportes", "Trabajo manual en reportes"]},
            ],
            client=client_mock,
            similarity_threshold=0.95,
        )

        self.assertEqual(2, len(clusters))
        self.assertEqual("pain-group-1", clusters[0]["group_id"])
        self.assertEqual(
            ["Trabajo manual en reportes", "Trabajo manual para reportes"],
            clusters[0]["source_pains"],
        )
        self.assertEqual(["Meeting A", "Meeting B"], clusters[0]["source_meetings"])
        self.assertEqual(["Falta de trazabilidad"], clusters[1]["source_pains"])


class EnrichmentTests(unittest.TestCase):
    def test_get_company_context_reads_context_from_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "company_context.txt"
            temp_path.write_text("Contexto de prueba", encoding="utf-8")

            with patch.object(
                insight_engine,
                "INSIGHT_ENGINE_COMPANY_CONTEXT",
                str(temp_path),
            ):
                company_context = insight_engine.get_company_context()

        self.assertEqual("Contexto de prueba", company_context)

    def test_get_insight_category_options_reads_categories_from_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "insight_category_options.txt"
            temp_path.write_text(
                "Categoria A\nCategoria B\nCategoria C\n",
                encoding="utf-8",
            )

            with patch.object(
                insight_engine,
                "INSIGHT_CATEGORY_OPTIONS",
                str(temp_path),
            ):
                options = insight_engine.get_insight_category_options()

        self.assertEqual(
            ["Categoria A", "Categoria B", "Categoria C"],
            options,
        )

    def test_enrich_pain_point_clusters_parses_structured_rows(self) -> None:
        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=json.dumps(
                            {
                                "rows": [
                                    {
                                        "group_id": "pain-group-1",
                                        "Categoria": "Operational efficiency and commercial strategy",
                                        "Dolores": "Existe trabajo manual para consolidar reportes comerciales",
                                        "ideas": [
                                            "Automatizar la consolidacion semanal de reportes comerciales",
                                            "Crear alertas sobre desvios de ventas y margen",
                                        ],
                                        "kpi_medicion": [
                                            "Horas semanales dedicadas a consolidacion",
                                            "Tiempo de cierre del reporte comercial",
                                        ],
                                        "Fuentes": ["Excel", "ERP", "Reportes comerciales"],
                                        "Tiempo_estimado": "3 to 6 weeks",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    )
                )
            ]
        )

        rows = insight_engine.enrich_pain_point_clusters(
            [
                {
                    "group_id": "pain-group-1",
                    "representative_pain": "Trabajo manual en reportes",
                    "source_pains": ["Trabajo manual en reportes", "Trabajo manual para reportes"],
                    "source_meetings": ["Meeting A", "Meeting B"],
                }
            ],
            client=client_mock,
            company_context="Contexto confidencial",
        )

        self.assertEqual(1, len(rows))
        self.assertEqual(
            "Operational efficiency and commercial strategy",
            rows[0]["Categoria"],
        )
        self.assertIn("Automatizar la consolidacion", rows[0]["ideas"])
        self.assertIn("Excel", rows[0]["Fuentes"])
        self.assertEqual("3 to 6 weeks", rows[0]["Tiempo_estimado"])


class DataframeAndCliTests(unittest.TestCase):
    @patch.object(insight_engine, "_load_pandas")
    @patch.object(insight_engine, "enrich_pain_point_clusters")
    @patch.object(insight_engine, "deduplicate_pain_points")
    def test_build_insight_dataframe_returns_expected_columns(
        self,
        deduplicate_mock: MagicMock,
        enrich_mock: MagicMock,
        load_pandas_mock: MagicMock,
    ) -> None:
        import pandas as pd

        load_pandas_mock.return_value = pd
        deduplicate_mock.return_value = [{"group_id": "pain-group-1"}]
        enrich_mock.return_value = [
            {
                "Categoria": "Information and visibility for decision-making",
                "Dolores": "Falta informacion confiable para decidir",
                "ideas": "Panel semanal con alertas",
                "kpi_medicion": "Tiempo de preparacion del informe",
                "Fuentes": "Excel\nERP",
                "Tiempo_estimado": "3 to 6 weeks",
            }
        ]

        dataframe = insight_engine.build_insight_dataframe([{"reunion": "A", "dolores": ["x"]}])

        self.assertEqual(insight_engine.OUTPUT_COLUMNS, dataframe.columns.tolist())
        self.assertEqual(1, len(dataframe))
        self.assertEqual(
            "Information and visibility for decision-making",
            dataframe.iloc[0]["Categoria"],
        )

    @patch.object(insight_engine, "build_refined_insight_dataframe")
    @patch.object(insight_engine, "load_structured_data")
    def test_main_prints_success_message(
        self,
        load_structured_data_mock: MagicMock,
        build_refined_dataframe_mock: MagicMock,
    ) -> None:
        import pandas as pd

        stdout = io.StringIO()
        load_structured_data_mock.return_value = [{"reunion": "A", "dolores": ["x"]}]
        build_refined_dataframe_mock.return_value = pd.DataFrame(
            [
                {
                    "Categoria": "Information and visibility for decision-making",
                    "Dolores": "Dolor consolidado",
                    "ideas": "Idea 1",
                    "kpi_medicion": "KPI 1",
                    "Fuentes": "Excel",
                    "Tiempo_estimado": "3 to 6 weeks",
                }
            ]
        )

        with patch("sys.argv", ["insight_engine.insight_engine", "/tmp/input.json"]), patch(
            "sys.stdout", stdout
        ):
            exit_code = insight_engine.main()

        self.assertEqual(0, exit_code)
        self.assertIn("Dataframe was generated successfully.", stdout.getvalue())

    @patch("insight_engine.export_data_to_google_sheet.export_dataframe_to_google_sheet")
    @patch.object(insight_engine, "build_refined_insight_dataframe")
    @patch.object(insight_engine, "load_structured_data")
    def test_main_exports_refined_dataframe(
        self,
        load_structured_data_mock: MagicMock,
        build_refined_dataframe_mock: MagicMock,
        export_dataframe_mock: MagicMock,
    ) -> None:
        import pandas as pd

        refined_dataframe = pd.DataFrame(
            [
                {
                    "Categoria": "Information and visibility for decision-making",
                    "Dolores": "Dolor refinado",
                    "ideas": "Idea refinada",
                    "kpi_medicion": "KPI refinado",
                    "Fuentes": "Excel",
                    "Tiempo_estimado": "3 to 6 weeks",
                }
            ]
        )
        load_structured_data_mock.return_value = [{"reunion": "A", "dolores": ["x"]}]
        build_refined_dataframe_mock.return_value = refined_dataframe
        export_dataframe_mock.return_value = "ok"

        with patch(
            "sys.argv",
            ["insight_engine.insight_engine", "/tmp/input.json", "--export-google-sheet"],
        ):
            exit_code = insight_engine.main()

        self.assertEqual(0, exit_code)
        export_dataframe_mock.assert_called_once()
        exported_dataframe = export_dataframe_mock.call_args.args[0]
        self.assertTrue(exported_dataframe.equals(refined_dataframe))


class ExportTests(unittest.TestCase):
    def test_extract_spreadsheet_key_accepts_key_or_url(self) -> None:
        self.assertEqual("abc123", export_data_to_google_sheet.extract_spreadsheet_key("abc123"))
        self.assertEqual(
            "abc123",
            export_data_to_google_sheet.extract_spreadsheet_key(
                "https://docs.google.com/spreadsheets/d/abc123/edit#gid=0"
            ),
        )

    def test_export_dataframe_to_google_sheet_writes_headers_and_rows(self) -> None:
        import pandas as pd

        dataframe = pd.DataFrame(
            [
                {
                    "Categoria": "Information and visibility for decision-making",
                    "Dolores": "Dolor consolidado",
                    "ideas": "Idea 1",
                    "kpi_medicion": "KPI 1",
                    "Fuentes": "Excel",
                    "Tiempo_estimado": "3 to 6 weeks",
                }
            ]
        )
        worksheet_mock = MagicMock()
        worksheet_mock.title = "Sheet1"
        worksheet_mock.get_all_values.return_value = []
        spreadsheet_mock = MagicMock(sheet1=worksheet_mock)
        spreadsheet_mock.worksheets.return_value = [worksheet_mock]
        client_mock = MagicMock()
        client_mock.open_by_key.return_value = spreadsheet_mock

        with patch.object(
            export_data_to_google_sheet,
            "get_google_sheets_client",
            return_value=client_mock,
        ):
            summary = export_data_to_google_sheet.export_dataframe_to_google_sheet(
                dataframe,
                spreadsheet_id="https://docs.google.com/spreadsheets/d/abc123/edit#gid=0",
            )

        worksheet_mock.clear.assert_not_called()
        worksheet_mock.update.assert_called_once()
        update_args = worksheet_mock.update.call_args[0]
        self.assertEqual("A1", update_args[0])
        self.assertEqual("Categoria", update_args[1][0][0])
        self.assertIn("Google Sheets export completed successfully", summary)
        self.assertIn("worksheet: Sheet1", summary)

    def test_export_dataframe_to_google_sheet_creates_new_sheet_when_target_has_content(self) -> None:
        import pandas as pd

        dataframe = pd.DataFrame(
            [
                {
                    "Categoria": "Information and visibility for decision-making",
                    "Dolores": "Dolor consolidado",
                    "ideas": "Idea 1",
                    "kpi_medicion": "KPI 1",
                    "Fuentes": "Excel",
                    "Tiempo_estimado": "3 to 6 weeks",
                }
            ]
        )
        existing_sheet_mock = MagicMock()
        existing_sheet_mock.title = "Sheet1"
        existing_sheet_mock.get_all_values.return_value = [["Categoria", "Dolores"]]
        new_sheet_mock = MagicMock()
        new_sheet_mock.title = "Sheet1_2"
        spreadsheet_mock = MagicMock(sheet1=existing_sheet_mock)
        spreadsheet_mock.worksheets.return_value = [existing_sheet_mock]
        spreadsheet_mock.add_worksheet.return_value = new_sheet_mock
        client_mock = MagicMock()
        client_mock.open_by_key.return_value = spreadsheet_mock

        with patch.object(
            export_data_to_google_sheet,
            "get_google_sheets_client",
            return_value=client_mock,
        ):
            summary = export_data_to_google_sheet.export_dataframe_to_google_sheet(
                dataframe,
                spreadsheet_id="https://docs.google.com/spreadsheets/d/abc123/edit#gid=0",
            )

        spreadsheet_mock.add_worksheet.assert_called_once_with(title="Sheet1_2", rows=1000, cols=26)
        existing_sheet_mock.update.assert_not_called()
        new_sheet_mock.update.assert_called_once()
        self.assertIn("worksheet: Sheet1_2", summary)


if __name__ == "__main__":
    unittest.main()
