# Contributing to Digiler AI

Thanks for your interest in improving Digiler AI. This document describes how to set up
the project and the standards contributions are expected to meet.

## Development setup

```bash
# Python platform (core)
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

# Backend API
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install
```

You will also need a local [Ollama](https://ollama.com) server with a model pulled
(default `qwen3`), and your own materials under `knowledge_base/raw/` (see
`knowledge_base/README.md`).

## Standards

- **Architecture is frozen (V3).** Make incremental, additive changes; do not redesign
  core components. Follow Clean Architecture and SOLID.
- **Every module ships tests and docs.** Reference resources by `resource_id`, never by
  absolute path. Raw materials are immutable; write only to `knowledge_base/derived/`.
- **Config over hardcode.** New behaviour should be configurable via `config/platform.yaml`.
- **No secrets in code.** Use environment variables.
- **Scientific integrity.** Never fabricate or manipulate evaluation metrics; report real
  results from real execution.

## Before opening a pull request

```bash
# platform tests
.\.venv\Scripts\python.exe -m pytest -q
# backend tests
cd backend && ..\.venv\Scripts\python.exe -m pytest -q
# frontend
cd frontend && npm run typecheck && npm run build
```

All tests must pass and the build must be clean. Describe what you changed, why, and how
you verified it.
