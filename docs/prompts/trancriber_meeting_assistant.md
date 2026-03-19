# Prompt: Add OpenAI transcription support (gpt-4o-transcribe)

Update the existing public Python repository `ai_assistants_lab` to support audio transcription for the `meeting_assistant` module using the OpenAI API and the model `gpt-4o-transcribe`.

## Goal

Implement a clean first iteration of the transcription layer for the meeting assistant, using OpenAI's transcription API in a modular and minimal way.

This repository is in a learning and prototyping phase, so keep the implementation simple, readable, and extensible. Avoid unnecessary abstractions.

## Important constraints

- Keep the repo public-friendly
- Do not hardcode secrets
- Use environment variables for configuration
- Do NOT create a real `.env` file
- Only use `.env.example` as reference
- Keep code simple and clean
- Python 3.10+
- Do not implement summarization or business logic yet
- Focus only on transcription

# Required Changes

This section defines the required modifications to implement audio transcription in the `meeting_assistant` module using the OpenAI API (`gpt-4o-transcribe`).

---

## 1) Update `common/config.py`

Extend the current configuration helpers to support transcription settings.

### Add:

- A helper function to retrieve the transcription model from environment variables:

def get_transcription_model() -> str:
    return get_env("OPENAI_TRANSCRIPTION_MODEL", default="gpt-4o-transcribe")

### Behavior:

- If OPENAI_TRANSCRIPTION_MODEL is defined → use it
- Otherwise → fallback to "gpt-4o-transcribe"
Keep the implementation consistent with the current style of get_env.

## 2) Use existing OpenAI client (common/llm_clients.py)

Use the existing function: "from common.llm_clients import create_openai_client"

No changes are required in this file unless strictly necessary.

## 3) Update meeting_assistant/transcriber.py

Replace placeholder logic with a real transcription implementation using OpenAI.

### Main funtion:
def transcribe_audio(file_path: str) -> str:

### Responsabilties:
- Validate that the file exists
- Validate supported file format
- Open the file safely
- Send the file to the OpenAI transcription API
- Return plain transcribed text

### Supported formats:
.mp3, .wav, .m4a

### Configuration:
- Use create_openai_client() for API access
- Use get_transcription_model() for model selection

### Error handling:
- File not found → raise clear error
- Unsupported format → raise clear error
- API failure → raise clear error

### Add a cli entry point:
bash:
python -m meeting_assistant.transcriber path/to/audio.mp3

## 4) OpenAI API usage

Use the OpenAI Python SDK for transcription.

### Expected pattern:

Python:
"
client = create_openai_client()

with open(file_path, "rb") as audio_file:
    response = client.audio.transcriptions.create(
        model=model,
        file=audio_file,
    )
"
Retun:
"
response.text
"

## 5) Updarte Requirements.txt

Ensure the following dependencies:
"
openai
python-dotenv
"
Do not add unnecessary libraries.

## 6) Update or create .env.example

Add the following variables:
"
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-transcribe
"

Do NOT create a real .env file.

## 7) Update meeting_assistant/README.md

- Transcription uses OpenAI API
- Required environment variables
- Example usage

## 8) Implementation guidelines
- Keep functions small and readable
- Add docstrings where useful
- Avoid unnecessary abstractions
- Do not introduce multi-provider architecture yet
- Write code that is easy to extend in future iterations

## 9) Scope control
- Do NOT implement summarization
- Do NOT modify prompts.py
- Do NOT add business logic
- Focus strictly on transcription
