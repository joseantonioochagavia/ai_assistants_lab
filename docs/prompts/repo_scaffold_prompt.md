# Repository Scaffold Prompt

Create the initial scaffold for a public Python repository named `ai_assistants_lab`.

## Goal

Set up a clean, professional repository that will host modular AI micro-tools, starting with a meeting assistant.

## Constraints

- Keep the repository minimal, readable, and public-repo friendly
- Add only placeholder code and lightweight helper functions
- Do not implement real business logic yet
- Target Python 3.10+
- Assume Git is already initialized locally

## Required Structure

```text
ai_assistants_lab/
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── common/
│   ├── __init__.py
│   ├── config.py
│   └── llm_clients.py
├── meeting_assistant/
│   ├── README.md
│   ├── __init__.py
│   ├── app.py
│   ├── transcriber.py
│   ├── summarizer.py
│   ├── prompts.py
│   └── tests/
│       └── __init__.py
├── docs/
│   └── prompts/
│       └── repo_scaffold_prompt.md
└── scripts/
    └── setup.sh
```

## File Expectations

- Root `README.md` with project summary, vision, current modules, roadmap, and philosophy
- Shared `common/` utilities for configuration and LLM client setup
- A scaffold-only `meeting_assistant/` module with placeholders for transcription, summarization, prompts, and app entry point
- A simple `scripts/setup.sh` script to create a virtual environment and install dependencies
- No secrets committed to the repository
