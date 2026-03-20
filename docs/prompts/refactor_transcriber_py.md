Refactor `meeting_assistant/transcriber.py` into a modular structure with 5 files, keeping current behavior unchanged.

## Goal
Improve clarity and maintainability by splitting responsibilities. Do NOT change logic or add features.

## Target structure
- `preprocess.py`
- `transcribe.py`
- `clean.py`
- `save.py`
- `app.py`

## Responsibilities

### preprocess.py
Audio utilities:
- file validation
- loading with `pydub`
- duration detection
- preprocessing (mono, sample rate)
- splitting into chunks

Move:
- `_validate_audio_path`
- `_load_audio_segment`
- `get_audio_duration_seconds`
- `preprocess_audio_for_transcription`
- `_split_audio_into_chunks`

---

### transcribe.py
Transcription logic:
- direct transcription (OpenAI)
- chunked transcription
- merge + deduplication of chunk outputs

Move:
- `transcribe_audio`
- `transcribe_audio_in_chunks`
- `merge_chunk_transcriptions`
+ related helper functions

---

### clean.py
LLM cleaning:
- `clean_transcription(raw_text)`
- model + system prompt

Use `create_openai_client()`. Do not modify behavior.

---

### save.py
Output handling:
- output directories
- `save_transcription_markdown`

Keep markdown format unchanged.

---

### app.py
Orchestration + CLI:
- `transcribe_audio_file`
- `main`

Flow:
input → preprocess → detect duration → transcribe → clean → save raw → save clean

CLI:
python -m meeting_assistant.app path/to/audio.m4a

## Constraints
- Preserve behavior
- No new features or dependencies
- No overengineering
- Prefer moving code, not rewriting
- Python 3.10+

Update README only if needed.