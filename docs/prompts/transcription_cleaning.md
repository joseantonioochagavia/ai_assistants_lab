## Goal

Implement a function that improves transcription quality by:

- fixing grammar and spelling
- removing filler words and noise
- restructuring spoken language into readable written text
- preserving the original meaning

This is NOT summarization. It is text cleaning and normalization.

## Important constraints

- Do NOT change meaning of the original text
- Do NOT summarize or remove important content
- Do NOT add new information
- Keep the output faithful to the original transcription
- Keep implementation simple and readable
- Use existing OpenAI client (`create_openai_client`)
- Python 3.10+
- Do not overengineer

---

## 1) Update `meeting_assistant/transcriber.py`

Add a new function:

python:
def clean_transcription(raw_text: str) -> str:

## Expected behavior:
- Expected behavior:
- Takes raw transcription text as input
- Returns cleaned and normalized text

## Use existing OpenAI client
Import and use
"
python:
from common.llm_clients import create_openai_client
"

Do NOT create a new client.

## Model configuration

Use: 
model = "gpt-4.1-mini"

## Prompt design
Use a strong system prompt like this:
"
You are an expert transcription editor.

Your task is to clean and normalize raw meeting transcriptions.

Rules:
- Preserve the original meaning exactly
- Do NOT summarize
- Do NOT remove important content
- Do NOT add new information

You must:
- Fix grammar and spelling
- Remove filler words (e.g., "eh", "mmm", "like", "weón" only if used as filler)
- Improve sentence structure
- Separate ideas into clear sentences or paragraphs
- Make the text readable and professional

Output:
- Return ONLY the cleaned text
- Do not include explanations
"

## API call structure
Use something like:
"
Python:
client = create_openai_client()

response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ],
    temperature=0.2,
)
"

Return:
"
Python:
response.choices[0].message.content
"

## Integrate into pipeline
Update your main transcription flow so that:
"
preprocessing → transcription → clean_transcription → save markdown
"

Ensure that: 
- the CLEANED version must be saved within outputs/transcripts/clean
- the raw version must be saved within outputs/transcripts/raw (just for debugging)

## Error handling
Add basic error handling:
- empty input → return empty string
- API failure → raise clear error

## Update README files
