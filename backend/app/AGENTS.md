<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# app

## Purpose
FastAPI application package. Owns HTTP routing, the SQLAlchemy data model, the AI generation pipeline, email rendering + Resend delivery, scheduling, authentication, and cryptography for stored secrets.

## Key Files
| File | Description |
|------|-------------|
| `main.py` | FastAPI app factory; runs `alembic upgrade head` on startup and mounts the API + static frontend |
| `config.py` | Pydantic `Settings` loaded from `PULSE_NEWS_*` environment variables |
| `database.py` | SQLAlchemy engine/session factory; exposes `get_session_maker()` and the `DbSession` dependency via `deps.py` |
| `deps.py` | FastAPI dependency providers (currently the DB session) |
| `models.py` | SQLAlchemy 2.x ORM models — `User`, `SystemSettings`, `Newsletter`, `NewsletterRecipient`, `NewsletterRun`, `NewsletterRunEvent`, `EmailTemplate`, `Provider`, `ApiKey`, `AuditEvent` |
| `schemas.py` | Pydantic v2 request/response models and enums (`SupportedProvider`, `NewsletterStatus`, ...) |
| `auth.py` | Session-cookie authentication, bootstrap gate, password hashing helpers |
| `security.py` | Password hashing (argon2/bcrypt via passlib) |
| `crypto.py` | Symmetric encryption of API key secrets at rest |
| `ai_generation.py` | Provider-agnostic content generation via litellm; returns a `GeneratedContent` with subject, preheader, body_text |
| `email_delivery.py` | Template rendering + Resend HTTP delivery; writes per-recipient outcomes onto the run |
| `email_templates.py` | Built-in template definitions (`signal`, `ledger`) and the renderer |
| `scheduler.py` | APScheduler wiring — `reconcile_scheduler_jobs`, `sync_newsletter_schedule`, startup reconciliation |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `api/` | FastAPI routers per resource — see `api/AGENTS.md` |

## For AI Agents

### Working In This Directory
- The newsletter send flow is single-step: `POST /newsletters/{id}/run` → `generate_newsletter_content` → mutate subject/preheader/body_text on the newsletter → `execute_newsletter_send`. Keep it single-step. A generation failure is a hard 422.
- No simulated/mock fallback code path. If the configured provider fails, the request fails — it does not fall back to a fake response.
- The backend fetches any URLs referenced in the prompt itself (the previous product relied on the LLM to fetch, which was fragile). If you add tools/plugins to the generation pipeline, preserve that invariant.
- Adjust `models.py` + generate a new Alembic migration + update the matching Pydantic schema in the same change. Never leave drift between those three.
- All mutations go through `create_audit_event` to produce a row in `AuditEvent` — keep that invariant for any new write endpoint.

### Testing Requirements
- Each module in this package has a matching `backend/tests/test_<module>.py`. New public functions need a corresponding test.

### Common Patterns
- Routers use `APIRouter(prefix="/resource", tags=["resource"])` and are aggregated in `api/router.py`.
- The DB session is injected as `db: DbSession` at every endpoint.
- Endpoints commit their own transaction and call `db.refresh()` before serializing.

## Dependencies

### Internal
- `alembic/versions/` — all schema changes must have a corresponding migration.

### External
- `fastapi`, `sqlalchemy`, `alembic`, `pydantic`, `APScheduler`, `litellm`, `httpx`, `passlib`, `cryptography`
