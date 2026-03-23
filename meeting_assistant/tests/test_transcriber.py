"""Tests for the meeting assistant transcription logic."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from meeting_assistant import app, clean, preprocess, save, transcribe


class TranscriberTests(unittest.TestCase):
    def test_clean_transcription_returns_empty_string_for_empty_input(self) -> None:
        self.assertEqual("", clean.clean_transcription(""))
        self.assertEqual("", clean.clean_transcription("   "))

    def test_clean_transcription_uses_openai_client(self) -> None:
        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Cleaned transcript"))]
        )

        with patch.object(clean, "create_openai_client", return_value=client_mock):
            cleaned_text = clean.clean_transcription("raw transcript")

        self.assertEqual("Cleaned transcript", cleaned_text)
        client_mock.chat.completions.create.assert_called_once_with(
            model=clean.CLEAN_TRANSCRIPTION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": clean.CLEAN_TRANSCRIPTION_SYSTEM_PROMPT,
                },
                {"role": "user", "content": "raw transcript"},
            ],
            temperature=0.2,
        )

    def test_preprocess_audio_for_transcription_exports_cleaned_wav(self) -> None:
        class FakeAudioSegment:
            def __init__(self) -> None:
                self.operations: list[tuple[str, int]] = []
                self.export_calls: list[tuple[Path, str]] = []

            def set_channels(self, channels: int) -> "FakeAudioSegment":
                self.operations.append(("set_channels", channels))
                return self

            def set_frame_rate(self, frame_rate: int) -> "FakeAudioSegment":
                self.operations.append(("set_frame_rate", frame_rate))
                return self

            def export(self, output_path: Path, format: str) -> None:
                self.export_calls.append((output_path, format))

        fake_audio = FakeAudioSegment()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "sample.mp3"
            audio_path.write_bytes(b"audio")

            with patch.object(preprocess, "_load_audio_segment", return_value=fake_audio):
                output_path = preprocess.preprocess_audio_for_transcription(
                    str(audio_path),
                    output_dir=temp_path / "preprocessed",
                )

        self.assertEqual(temp_path / "preprocessed" / "sample_preprocessed.wav", output_path)
        self.assertEqual(
            [
                ("set_channels", preprocess.PREPROCESSED_CHANNELS),
                ("set_frame_rate", preprocess.PREPROCESSED_SAMPLE_RATE_HZ),
            ],
            fake_audio.operations,
        )
        self.assertEqual([(output_path, "wav")], fake_audio.export_calls)

    def test_split_audio_into_chunks_adds_overlap(self) -> None:
        class FakeChunk:
            def __init__(
                self,
                start_ms: int,
                end_ms: int,
                export_calls: list[tuple[int, int, Path, str]],
            ) -> None:
                self.start_ms = start_ms
                self.end_ms = end_ms
                self.export_calls = export_calls

            def export(self, output_path: Path, format: str) -> None:
                self.export_calls.append((self.start_ms, self.end_ms, output_path, format))

        class FakeAudioSegment:
            def __init__(self, duration_ms: int) -> None:
                self.duration_ms = duration_ms
                self.export_calls: list[tuple[int, int, Path, str]] = []

            def __len__(self) -> int:
                return self.duration_ms

            def __getitem__(self, item: slice) -> FakeChunk:
                start_ms = 0 if item.start is None else item.start
                end_ms = self.duration_ms if item.stop is None else min(item.stop, self.duration_ms)
                return FakeChunk(start_ms, end_ms, self.export_calls)

        fake_audio = FakeAudioSegment(duration_ms=50000)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "sample.wav"
            audio_path.write_bytes(b"audio")

            with (
                patch.object(preprocess, "_load_audio_segment", return_value=fake_audio),
                patch.object(preprocess, "CHUNK_OVERLAP_SECONDS", 5),
            ):
                chunk_metadata = preprocess._split_audio_into_chunks(
                    str(audio_path),
                    chunk_duration_seconds=20,
                    output_dir=temp_path / "chunks",
                )

        self.assertEqual(
            [(1, 0, 20000), (2, 15000, 35000), (3, 30000, 50000)],
            [(chunk.index, chunk.start_ms, chunk.end_ms) for chunk in chunk_metadata],
        )
        self.assertEqual(
            [(0, 20000), (15000, 35000), (30000, 50000)],
            [(start_ms, end_ms) for start_ms, end_ms, _, _ in fake_audio.export_calls],
        )

    def test_merge_chunk_transcriptions_removes_overlap_between_chunks(self) -> None:
        chunk_transcriptions = [
            (
                "Primera idea con bastante detalle para superar el umbral y dejar claro el cierre.\n"
                "Seguimos con una segunda linea extensa para que el empalme sea evidente.\n"
                "Tercera linea con mas contexto para cerrar el primer chunk con suficiente texto."
            ),
            (
                "Seguimos con una segunda linea extensa para que el empalme sea evidente.\n"
                "Tercera linea con mas contexto para cerrar el primer chunk con suficiente texto.\n"
                "Cuarta linea ya exclusiva del siguiente chunk y sin duplicados."
            ),
        ]

        merged_transcription = transcribe.merge_chunk_transcriptions(chunk_transcriptions)

        self.assertEqual(
            (
                "Primera idea con bastante detalle para superar el umbral y dejar claro el cierre.\n"
                "Seguimos con una segunda linea extensa para que el empalme sea evidente.\n"
                "Tercera linea con mas contexto para cerrar el primer chunk con suficiente texto.\n"
                "Cuarta linea ya exclusiva del siguiente chunk y sin duplicados."
            ),
            merged_transcription,
        )

    def test_merge_chunk_transcriptions_removes_repeated_adjacent_blocks(self) -> None:
        repeated_block = (
            "Primera linea larga de prueba para representar una seccion repetida del transcript.\n"
            "Segunda linea larga de prueba para representar una seccion repetida del transcript.\n"
            "Tercera linea larga de prueba para representar una seccion repetida del transcript."
        )

        merged_transcription = transcribe.merge_chunk_transcriptions(
            [f"{repeated_block}\n{repeated_block}\nLinea final sin repetir."]
        )

        self.assertEqual(
            f"{repeated_block}\nLinea final sin repetir.",
            merged_transcription,
        )

    def test_merge_chunk_transcriptions_keeps_unclear_overlap(self) -> None:
        first_chunk = (
            "Primera idea con bastante detalle para dejar claro el primer tramo del audio.\n"
            "Segunda idea con bastante detalle para dejar claro el primer tramo del audio.\n"
            "Tercera idea con bastante detalle para dejar claro el primer tramo del audio."
        )
        second_chunk = (
            "Segunda idea con una variacion menor para dejar claro el segundo tramo del audio.\n"
            "Tercera idea con una variacion menor para dejar claro el segundo tramo del audio.\n"
            "Cuarta idea completamente nueva para cerrar el segundo tramo del audio."
        )

        merged_transcription = transcribe.merge_chunk_transcriptions([first_chunk, second_chunk])

        self.assertIn(
            "Segunda idea con bastante detalle para dejar claro el primer tramo del audio.",
            merged_transcription,
        )
        self.assertIn(
            "Segunda idea con una variacion menor para dejar claro el segundo tramo del audio.",
            merged_transcription,
        )

    def test_transcribe_audio_in_chunks_saves_debug_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "sample.wav"
            audio_path.write_bytes(b"audio")
            debug_artifacts = save.DebugArtifacts(
                root_dir=temp_path / "debug" / "sample",
                original_audio_dir=temp_path / "debug" / "sample" / "audio" / "original",
                preprocessed_audio_dir=temp_path / "debug" / "sample" / "audio" / "preprocessed",
                chunk_audio_dir=temp_path / "debug" / "sample" / "audio" / "chunks",
                transcript_dir=temp_path / "debug" / "sample" / "transcripts",
                chunk_transcript_dir=temp_path / "debug" / "sample" / "transcripts" / "chunks",
            )
            chunk_metadata = [
                preprocess.AudioChunk(
                    index=1,
                    start_ms=0,
                    end_ms=20000,
                    path=temp_path / "chunk_001.wav",
                ),
                preprocess.AudioChunk(
                    index=2,
                    start_ms=15000,
                    end_ms=35000,
                    path=temp_path / "chunk_002.wav",
                ),
            ]
            chunk_transcriptions = [
                (
                    "Primera idea con bastante detalle para superar el umbral del merge.\n"
                    "Segunda idea con bastante detalle para superar el umbral del merge.\n"
                    "Tercera idea con bastante detalle para superar el umbral del merge."
                ),
                (
                    "Segunda idea con bastante detalle para superar el umbral del merge.\n"
                    "Tercera idea con bastante detalle para superar el umbral del merge.\n"
                    "Cuarta idea nueva para cerrar el segundo chunk sin perder contenido."
                ),
            ]

            with (
                patch.object(transcribe, "_split_audio_into_chunks", return_value=chunk_metadata),
                patch.object(transcribe, "transcribe_audio", side_effect=chunk_transcriptions),
                patch.object(transcribe, "save_chunk_debug_transcription") as save_chunk_debug_mock,
            ):
                merged_transcription = transcribe.transcribe_audio_in_chunks(
                    str(audio_path),
                    debug_source_path=str(audio_path),
                    debug_artifacts=debug_artifacts,
                )

        self.assertIn(
            "Primera idea con bastante detalle para superar el umbral del merge.",
            merged_transcription,
        )
        self.assertIn(
            "Cuarta idea nueva para cerrar el segundo chunk sin perder contenido.",
            merged_transcription,
        )
        self.assertEqual(2, save_chunk_debug_mock.call_count)
        self.assertEqual(
            [
                call(
                    str(audio_path),
                    1,
                    0,
                    20000,
                    chunk_transcriptions[0],
                    output_dir=debug_artifacts.chunk_transcript_dir,
                    chunk_file_name="chunk_001.wav",
                ),
                call(
                    str(audio_path),
                    2,
                    15000,
                    35000,
                    chunk_transcriptions[1],
                    output_dir=debug_artifacts.chunk_transcript_dir,
                    chunk_file_name="chunk_002.wav",
                ),
            ],
            save_chunk_debug_mock.call_args_list,
        )

    def test_transcribe_audio_file_uses_direct_transcription_for_short_audio(self) -> None:
        with (
            patch.object(app, "_validate_audio_path", return_value=Path("sample.mp3")),
            patch.object(app, "get_audio_duration_seconds", return_value=600),
            patch.object(app, "transcribe_audio", return_value="short transcript") as direct_mock,
            patch.object(
                app,
                "clean_transcription",
                return_value="clean short transcript",
            ) as clean_mock,
            patch.object(
                app,
                "transcribe_audio_in_chunks",
                return_value="chunked transcript",
            ) as chunked_mock,
            patch.object(
                app,
                "save_transcription_markdown",
                side_effect=[Path("/tmp/raw.md"), Path("/tmp/clean.md")],
            ) as save_mock,
            patch.object(app, "preprocess_audio_for_transcription") as preprocess_mock,
        ):
            transcription, output_path = app.transcribe_audio_file("sample.mp3")

        self.assertEqual("clean short transcript", transcription)
        self.assertEqual(Path("/tmp/clean.md"), output_path)
        preprocess_mock.assert_not_called()
        direct_mock.assert_called_once_with("sample.mp3")
        clean_mock.assert_called_once_with("short transcript")
        chunked_mock.assert_not_called()
        self.assertEqual(
            [
                call("sample.mp3", "short transcript", output_dir=app.RAW_OUTPUTS_DIR),
                call(
                    "sample.mp3",
                    "clean short transcript",
                    output_dir=app.CLEAN_OUTPUTS_DIR,
                ),
            ],
            save_mock.call_args_list,
        )

    def test_transcribe_audio_file_uses_chunked_transcription_for_long_audio(self) -> None:
        with (
            patch.object(app, "_validate_audio_path", return_value=Path("sample.mp3")),
            patch.object(app, "get_audio_duration_seconds", return_value=1800),
            patch.object(app, "transcribe_audio") as direct_mock,
            patch.object(
                app,
                "transcribe_audio_in_chunks",
                return_value="raw chunked transcript",
            ) as chunked_mock,
            patch.object(
                app,
                "clean_transcription",
                return_value="clean chunked transcript",
            ) as clean_mock,
            patch.object(
                app,
                "save_transcription_markdown",
                side_effect=[Path("/tmp/raw.md"), Path("/tmp/clean.md")],
            ) as save_mock,
            patch.object(app, "preprocess_audio_for_transcription") as preprocess_mock,
        ):
            transcription, output_path = app.transcribe_audio_file("sample.mp3")

        self.assertEqual("clean chunked transcript", transcription)
        self.assertEqual(Path("/tmp/clean.md"), output_path)
        preprocess_mock.assert_not_called()
        direct_mock.assert_not_called()
        chunked_mock.assert_called_once_with("sample.mp3")
        clean_mock.assert_called_once_with("raw chunked transcript")
        self.assertEqual(
            [
                call(
                    "sample.mp3",
                    "raw chunked transcript",
                    output_dir=app.RAW_OUTPUTS_DIR,
                ),
                call(
                    "sample.mp3",
                    "clean chunked transcript",
                    output_dir=app.CLEAN_OUTPUTS_DIR,
                ),
            ],
            save_mock.call_args_list,
        )

    def test_transcribe_audio_file_debug_mode_saves_pipeline_artifacts(self) -> None:
        debug_artifacts = save.DebugArtifacts(
            root_dir=Path("/tmp/debug/sample"),
            original_audio_dir=Path("/tmp/debug/sample/audio/original"),
            preprocessed_audio_dir=Path("/tmp/debug/sample/audio/preprocessed"),
            chunk_audio_dir=Path("/tmp/debug/sample/audio/chunks"),
            transcript_dir=Path("/tmp/debug/sample/transcripts"),
            chunk_transcript_dir=Path("/tmp/debug/sample/transcripts/chunks"),
        )

        with (
            patch.object(app, "_validate_audio_path", return_value=Path("sample.mp3")),
            patch.object(app, "prepare_debug_artifacts", return_value=debug_artifacts) as prepare_mock,
            patch.object(app, "get_debug_artifacts", return_value=debug_artifacts),
            patch.object(app, "save_debug_audio_artifact") as save_audio_debug_mock,
            patch.object(
                app,
                "preprocess_audio_for_transcription",
                return_value=Path("/tmp/sample_preprocessed.wav"),
            ) as preprocess_mock,
            patch.object(app, "get_audio_duration_seconds", return_value=1800),
            patch.object(app, "transcribe_audio") as direct_mock,
            patch.object(
                app,
                "transcribe_audio_in_chunks",
                return_value="raw chunked transcript",
            ) as chunked_mock,
            patch.object(
                app,
                "clean_transcription",
                return_value="clean chunked transcript",
            ) as clean_mock,
            patch.object(app, "save_merged_raw_debug_transcription") as save_merged_debug_mock,
            patch.object(app, "save_cleaned_debug_transcription") as save_cleaned_debug_mock,
            patch.object(
                app,
                "save_transcription_markdown",
                side_effect=[Path("/tmp/raw.md"), Path("/tmp/clean.md")],
            ) as save_mock,
        ):
            transcription, output_path = app.transcribe_audio_file("sample.mp3", debug=True)

        self.assertEqual("clean chunked transcript", transcription)
        self.assertEqual(Path("/tmp/clean.md"), output_path)
        prepare_mock.assert_called_once_with("sample.mp3")
        save_audio_debug_mock.assert_called_once_with(
            Path("sample.mp3"),
            debug_artifacts.original_audio_dir,
        )
        preprocess_mock.assert_called_once_with(
            "sample.mp3",
            output_dir=debug_artifacts.preprocessed_audio_dir,
        )
        direct_mock.assert_not_called()
        chunked_mock.assert_called_once_with(
            "sample.mp3",
            debug_source_path="sample.mp3",
            debug_artifacts=debug_artifacts,
        )
        clean_mock.assert_called_once_with("raw chunked transcript")
        save_merged_debug_mock.assert_called_once_with(
            "sample.mp3",
            "raw chunked transcript",
            output_path=debug_artifacts.transcript_dir / "merged_raw.md",
        )
        save_cleaned_debug_mock.assert_called_once_with(
            "sample.mp3",
            "clean chunked transcript",
            output_path=debug_artifacts.transcript_dir / "cleaned.md",
        )
        self.assertEqual(
            [
                call(
                    "sample.mp3",
                    "raw chunked transcript",
                    output_dir=app.RAW_OUTPUTS_DIR,
                ),
                call(
                    "sample.mp3",
                    "clean chunked transcript",
                    output_dir=app.CLEAN_OUTPUTS_DIR,
                ),
            ],
            save_mock.call_args_list,
        )

    def test_save_transcription_markdown_writes_expected_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "sample.mp3"
            audio_path.write_bytes(b"audio")

            output_path = save.save_transcription_markdown(
                str(audio_path),
                "hello world",
                output_dir=temp_path / "outputs" / "transcripts" / "clean",
            )

            self.assertEqual(
                temp_path / "outputs" / "transcripts" / "clean" / "sample.md",
                output_path,
            )
            self.assertEqual(
                "# Transcription\n\n"
                "Source file: sample.mp3\n\n"
                "---\n\n"
                "hello world\n",
                output_path.read_text(encoding="utf-8"),
            )

    def test_prepare_debug_artifacts_creates_clean_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_path = temp_path / "sample.mp3"
            audio_path.write_bytes(b"audio")
            debug_root = temp_path / "outputs" / "debug"
            stale_file = debug_root / "sample" / "stale.txt"
            stale_file.parent.mkdir(parents=True, exist_ok=True)
            stale_file.write_text("stale", encoding="utf-8")

            with patch.object(save, "DEBUG_OUTPUTS_DIR", debug_root):
                debug_artifacts = save.prepare_debug_artifacts(str(audio_path))

            self.assertFalse(stale_file.exists())
            self.assertTrue(debug_artifacts.original_audio_dir.is_dir())
            self.assertTrue(debug_artifacts.preprocessed_audio_dir.is_dir())
            self.assertTrue(debug_artifacts.chunk_audio_dir.is_dir())
            self.assertTrue(debug_artifacts.transcript_dir.is_dir())
            self.assertTrue(debug_artifacts.chunk_transcript_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
