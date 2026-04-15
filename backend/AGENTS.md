<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# backend

## Purpose
Python 3.13 FastAPI service that owns the newsletter data model, the AI generation pipeline, email rendering, Resend delivery, scheduling, and the operator auth/session layer. It exposes a JSON API under `/api/*` and is also responsible for serving the built frontend in the Docker image.

## Key Files
| File | Description |
|------|-------------|
| `pyproject.toml` | Package definition, runtime deps, and `[dev]` tools (ruff, pytest) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `app/` | Application code (routers, models, services) — see `app/AGENTS.md` |
| `tests/` | Pytest suite — see `tests/AGENTS.md` |

## For AI Agents

### Working In This Directory
- Always run `ruff check .` and `ruff format --check .` before committing; CI fails on either.
- Dependencies installed via `pip install -e ".[dev]"`.
- Python version is 3.13 — `StrEnum`, `datetime.UTC`, and modern union syntax are used throughout.
- Do not add provider-specific branches to route handlers. Provider differences live in `app/ai_generation.py` behind a single `generate_newsletter_content` entry point; email delivery differences live in `app/email_delivery.py`.

### Testing Requirements
- `cd backend && pytest -v --tb=short` — full suite is expected to pass in under ~2 minutes.
- Tests run against an in-memory SQLite instance by default; there is no Docker requirement for unit tests.

### Common Patterns
- Each HTTP resource lives in its own module under `app/api/`, exported via `app/api/router.py`.
- Sessions are cookie-based; endpoints get `require_authenticated_user(request, db)` at the top of the handler.
- Pydantic `*CreateRequest` / `*UpdateRequest` / `*Summary` / `*Detail` class pairs.

## Dependencies

### Internal
- None above this directory.

### External
- `fastapi`, `uvicorn`, `starlette`, `sqlalchemy`, `alembic`, `pydantic`, `APScheduler`, `litellm`, `httpx`, `ruff`, `pytest`
