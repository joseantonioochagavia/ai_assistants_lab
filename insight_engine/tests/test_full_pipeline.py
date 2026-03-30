"""Tests for the full audio-to-Google-Sheets pipeline CLI."""

from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from insight_engine import full_pipeline


class FullPipelineTests(unittest.TestCase):
    @patch("insight_engine.full_pipeline.export_dataframe_to_google_sheet")
    @patch("insight_engine.full_pipeline.build_refined_insight_dataframe")
    @patch("insight_engine.full_pipeline.extract_structured_data_from_files")
    @patch("insight_engine.full_pipeline.transcribe_multiple_audio_files")
    def test_run_full_pipeline_uses_only_transcripts_from_requested_audio_files(
        self,
        transcribe_mock: MagicMock,
        extract_mock: MagicMock,
        build_mock: MagicMock,
        export_mock: MagicMock,
    ) -> None:
        import pandas as pd

        first_output_path = Path("/tmp/clean/audio_1.md")
        second_output_path = Path("/tmp/clean/audio_2.md")
        transcribe_mock.return_value = (
            [
                ("audio_1.mp3", Path("/tmp/audio_1.mp3"), first_output_path),
                ("audio_2.mp3", Path("/tmp/audio_2.mp3"), second_output_path),
            ],
            [],
        )
        extract_mock.return_value = [{"reunion": "A", "dolores": ["x"], "temas_clave": ["y"]}]
        build_mock.return_value = pd.DataFrame(
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
        export_mock.return_value = "ok"

        export_summary, refined_dataframe = full_pipeline.run_full_pipeline(
            ["audio_1.mp3", "audio_2.mp3"],
            worksheet_name="Sheet1",
        )

        self.assertEqual("ok", export_summary)
        self.assertEqual(1, len(refined_dataframe))
        extract_mock.assert_called_once_with([first_output_path, second_output_path])
        export_mock.assert_called_once()

    @patch("insight_engine.full_pipeline.export_dataframe_to_google_sheet")
    @patch("insight_engine.full_pipeline.build_refined_insight_dataframe")
    @patch("insight_engine.full_pipeline.extract_structured_data_from_files")
    @patch("insight_engine.full_pipeline.transcribe_multiple_audio_files")
    def test_run_full_pipeline_aborts_on_transcription_failure(
        self,
        transcribe_mock: MagicMock,
        extract_mock: MagicMock,
        build_mock: MagicMock,
        export_mock: MagicMock,
    ) -> None:
        transcribe_mock.return_value = (
            [],
            [("broken.mp3", RuntimeError("transcription failed"))],
        )

        with self.assertRaises(RuntimeError) as context:
            full_pipeline.run_full_pipeline(["broken.mp3"])

        self.assertIn("broken.mp3", str(context.exception))
        extract_mock.assert_not_called()
        build_mock.assert_not_called()
        export_mock.assert_not_called()

    @patch("insight_engine.full_pipeline.get_refinement_metadata")
    @patch("insight_engine.full_pipeline.run_full_pipeline")
    def test_main_prints_pipeline_summary(
        self,
        run_full_pipeline_mock: MagicMock,
        get_refinement_metadata_mock: MagicMock,
    ) -> None:
        import pandas as pd

        stdout = io.StringIO()
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
        run_full_pipeline_mock.return_value = ("export ok", refined_dataframe)
        get_refinement_metadata_mock.return_value = {
            "scores": [72, 84],
            "best_score": 84,
        }

        with patch(
            "sys.argv",
            ["insight_engine.full_pipeline", "audio_1.mp3", "audio_2.mp3", "--worksheet-name", "Sheet1"],
        ), patch("sys.stdout", stdout):
            exit_code = full_pipeline.main()

        self.assertEqual(0, exit_code)
        self.assertIn("audio_1.mp3: processed successfully", stdout.getvalue())
        self.assertIn("audio_2.mp3: processed successfully", stdout.getvalue())
        self.assertIn("scores: 72 -> 84", stdout.getvalue())
        self.assertIn("export ok", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
