# ai_assistants_lab

A public Python repository for small, modular AI assistants focused on workflow automation.

## Vision

This repository is a personal lab for building practical AI assistants that solve focused workflow problems in a clean, reusable, and maintainable way.

## Current Modules

- `meeting_assistant`: scaffold for a future assistant that can help transcribe, summarize, and organize meeting outputs.

## Setup

Install the initial development environment with:

```bash
make install
```

## Roadmap

- Add the first working meeting assistant flow
- Introduce shared utilities for LLM access and configuration
- Expand the lab with additional workflow-oriented assistants
- Add tests and lightweight developer tooling as modules mature

## Repository Philosophy

- Modular: each assistant lives in its own directory with clear boundaries
- Simple: start with minimal scaffolding before adding real logic
- Extensible: shared utilities should support future assistants without forcing early abstractions
