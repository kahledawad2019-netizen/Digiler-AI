# Security Policy

## Reporting a vulnerability

If you discover a security issue, please open a private report via GitHub Security
Advisories (Security tab → "Report a vulnerability") or contact the maintainers directly
rather than filing a public issue. We aim to acknowledge reports promptly.

## Secrets and credentials

This repository ships **no secrets**. All credentials are supplied at runtime through
environment variables, never committed:

- `DIGILER_SECRET_KEY` — JWT signing key (set a long random value in production)
- `ALA_LLM_BASE_URL` / `ALA_LLM_MODEL` — local Ollama endpoint and model
- `ALA_RESEARCH_PROVIDER` / `ALA_RESEARCH_API_KEY` — optional web-search provider

Copy `backend/.env.example` to `backend/.env` and fill in your own values. Never commit
`.env` files, API keys, OAuth client secrets, or database files — they are git-ignored.

## Operational notes

- The default vector store is **Qdrant in local (single-process) mode**. Run exactly one
  backend worker, or switch to Qdrant server mode for concurrency.
- The function-calling runtime executes only AST-validated, sandboxed operations
  (calculator, restricted Python) with a whitelist and a hard execution deadline.
- Authentication uses JWT access + refresh tokens with bcrypt password hashing and
  role-based access control (student / instructor / admin).
