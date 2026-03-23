"""Tests for structured transcript extraction."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from insight_engine import data_extraction


class DataExtractionTests(unittest.TestCase):
    def test_read_transcript_markdown_returns_transcript_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript_path = Path(temp_dir) / "sample.md"
            transcript_path.write_text(
                "# Transcription\n\n"
                "Source file: sample.mp3\n\n"
                "---\n\n"
                "Pain point one.\nPain point two.\n",
                encoding="utf-8",
            )

            transcript_body = data_extraction.read_transcript_markdown(transcript_path)

        self.assertEqual("Pain point one.\nPain point two.", transcript_body)

    def test_extract_structured_fields_uses_openai_and_parses_json(self) -> None:
        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"dolores": ["Mucho trabajo manual", "Falta de trazabilidad"]}'
                    )
                )
            ]
        )

        with patch.object(data_extraction, "create_openai_client", return_value=client_mock):
            payload = data_extraction.extract_structured_fields("Transcript text")

        self.assertEqual(
            {"dolores": ["Mucho trabajo manual", "Falta de trazabilidad"]},
            payload,
        )
        client_mock.chat.completions.create.assert_called_once()

    def test_extract_structured_data_iterates_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            transcripts_dir = Path(temp_dir)
            (transcripts_dir / "B Meeting.md").write_text(
                "# Transcription\n\nSource file: b.mp3\n\n---\n\nTexto B",
                encoding="utf-8",
            )
            (transcripts_dir / "A Meeting.md").write_text(
                "# Transcription\n\nSource file: a.mp3\n\n---\n\nTexto A",
                encoding="utf-8",
            )

            with patch.object(
                data_extraction,
                "extract_structured_fields",
                side_effect=[
                    {"dolores": ["Dolor A"]},
                    {"dolores": ["Dolor B"]},
                ],
            ) as extract_mock:
                structured_data = data_extraction.extract_structured_data(transcripts_dir)

        self.assertEqual(
            [
                {"reunion": "A Meeting", "dolores": ["Dolor A"]},
                {"reunion": "B Meeting", "dolores": ["Dolor B"]},
            ],
            structured_data,
        )
        self.assertEqual(2, extract_mock.call_count)

    def test_main_prints_structured_json(self) -> None:
        stdout = io.StringIO()

        with (
            patch.object(
                data_extraction,
                "extract_structured_data",
                return_value=[{"reunion": "Samuel Hurtado", "dolores": ["Falta de tiempo"]}],
            ),
            patch("sys.argv", ["insight_engine.data_extraction", "/tmp/transcripts"]),
            patch("sys.stdout", stdout),
        ):
            exit_code = data_extraction.main()

        self.assertEqual(0, exit_code)
        self.assertIn('"reunion": "Samuel Hurtado"', stdout.getvalue())
        self.assertIn('"dolores": [', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
