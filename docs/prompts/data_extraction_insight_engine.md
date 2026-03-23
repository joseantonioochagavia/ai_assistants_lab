Implement the first step of `insight_engine`: structured extraction from cleaned meeting transcripts.

## Goal
Inside `insight_engine/data_extraction.py`, create logic that iterates over all cleaned transcript `.md` files (meeting_assistant/outputs/clean) and returns a structured list where each element is a dictionary with:

- `"reunion"`: string with the meeting name, derived from the filename
- `"dolores"`: list of pain points identified from that transcript using OpenAI

## Requirements

- Use a configurable prompt variable (do not hardcode pain extraction directly inside the function)
- Design it so the prompt can be replaced later for other extraction tasks, not only pain detection
- Keep code simple, modular, and readable
- Reuse existing OpenAI client helper from `common.llm_clients`
- Reuse existing repo style
- Do not build clustering, categorization, or insights yet
- Focus only on meeting-level structured extraction

## Suggested behavior

High-level flow:

1. Iterate over `.md` files in meeting_assistant/outputs/clean
2. Read transcript text
3. Extract meeting name from filename
4. Send transcript text to LLM using a prompt variable
5. Return a Python list like:

python:
[
    {
        "reunion": "Samuel Hurtado",
        "dolores": ["pain 1", "pain 2"]
    }
]


## Promt design

Create a prompt variable that is easy to modify later, for example:
- system prompt constant
- task prompt constant
- or function argument with default

The LLM output should be easy to parse and robust. Prefer a structured output format.

## CLI requirement

Add a simple CLI entry point to execute this module and return the structured list.

- Implement a function like:
python:
def extract_structured_data(input_dir: str) -> list[dict]:

- add a CLI interface in the same file:
python -m insight_engine.data_structured path/to/transcripts