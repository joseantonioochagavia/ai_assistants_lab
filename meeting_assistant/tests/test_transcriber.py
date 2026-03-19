"""Tests for the meeting assistant transcription logic."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from meeting_assistant import transcriber


class TranscriberTests(unittest.TestCase):
    def test_transcribe_audio_file_uses_direct_transcription_for_short_audio(self) -> None:
        with (
            patch.object(transcriber, "get_audio_duration_seconds", return_value=600),
            patch.object(transcriber, "transcribe_audio", return_value="short transcript") as direct_mock,
            patch.object(
                transcriber,
                "transcribe_audio_in_chunks",
                return_value="chunked transcript",
            ) as chunked_mock,
            patch.object(
                transcriber,
                "save_transcription_markdown",
                return_value=Path("/tmp/direct.md"),
            ) as save_mock,
        ):
            transcription, output_path = transcriber.transcribe_audio_file("sample.mp3")

        self.assertEqual("short transcript", transcription)
        self.assertEqual(Path("/tmp/direct.md"), output_path)
        direct_mock.assert_called_once_with("sample.mp3")
        chunked_mock.assert_not_called()
        save_mock.assert_called_once_with("sample.mp3", "short transcript")

    def test_transcribe_audio_file_uses_chunked_transcription_for_long_audio(self) -> None:
        with (
            patch.object(transcriber, "get_audio_duration_seconds", return_value=1800),
            patch.object(transcriber, "transcribe_audio") as direct_mock,
            patch.object(
                transcriber,
                "transcribe_audio_in_chunks",
                return_value="chunked transcript",
            ) as chunked_mock,
            patch.object(
                transcriber,
                "save_transcription_markdown",
                return_value=Path("/tmp/chunked.md"),
            ) as save_mock,
        ):
            transcription, output_path = transcriber.transcribe_audio_file("sample.mp3")

        self.assertEqual("chunked transcript", transcription)
        self.assertEqual(Path("/tmp/chunked.md"), output_path)
        direct_mock.assert_not_called()
        chunked_mock.assert_called_once_with("sample.mp3")
        save_mock.assert_called_once_with("sample.mp3", "chunked transcript")

    def test_save_transcription_markdown_writes_expected_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "sample.mp3"
            audio_path.write_bytes(b"audio")

            with patch.object(transcriber, "OUTPUTS_DIR", temp_path / "outputs" / "transcripts"):
                output_path = transcriber.save_transcription_markdown(
                    str(audio_path),
                    "hello world",
                )

            self.assertEqual(temp_path / "outputs" / "transcripts" / "sample.md", output_path)
            self.assertEqual(
                "# Transcription\n\n"
                "Source file: sample.mp3\n\n"
                "---\n\n"
                "hello world\n",
                output_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
