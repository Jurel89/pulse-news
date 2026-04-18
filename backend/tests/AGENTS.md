<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# tests

## Purpose
Pytest suite for the backend. Runs against an in-memory SQLite fixture; no Docker or external services are required. Covers HTTP routes, the AI generation wrapper, email delivery, the scheduler, webhooks, migrations, and auth.

## Key Files
| File | Description |
|------|-------------|
| `test_newsletters.py` | CRUD, run, schedule pause/resume, archive, delete |
| `test_runs.py` | Run listing, filtering, detail retrieval |
| `test_ai_generation.py` | Provider-agnostic generation wrapper with mocked litellm |
| `test_email_delivery.py` | Template rendering + Resend HTTP client (mocked transport) |
| `test_email_templates.py` | Built-in template CRUD and rendering |
| `test_auth.py` | Bootstrap, login, logout, session |
| `test_webhooks.py` | Resend webhook event handling |
| `test_scheduler.py` | APScheduler reconciliation on startup and on newsletter changes |
| `test_database_migrations.py` | Alembic chain builds a valid schema from scratch |
| `test_audit_phase0.py` | Audit event write-path for every mutation route |

## For AI Agents

### Working In This Directory
- Every new public function or route needs a test here.
- Prefer using the FastAPI `TestClient` over fabricating ASGI calls manually.
- Tests must run fast — avoid `time.sleep`, real HTTP calls, or real Resend/AI-provider traffic. Mock `litellm.completion` and the Resend HTTP client.

### Testing Requirements
- `cd backend && pytest -v --tb=short` from the backend dir.
- CI fails on any test failure or collection error (see `backend-test` job in `.github/workflows/ci.yml`).

### Common Patterns
- Fixtures for an authenticated client, a seeded provider/api-key pair, and a newsletter live at module scope.

## Dependencies

### Internal
- Everything under `../app/`.

### External
- `pytest`, `httpx` (via FastAPI's `TestClient`)
