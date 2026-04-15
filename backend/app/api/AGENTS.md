<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# api

## Purpose
FastAPI routers — one module per resource. Each module exports a single `APIRouter` that is aggregated in `router.py` and mounted at `/api` by `app/main.py`.

## Key Files
| File | Description |
|------|-------------|
| `router.py` | Aggregates every resource router into `api_router` |
| `auth.py` | `/auth/bootstrap`, `/auth/login`, `/auth/logout`, `/auth/session`, `/auth/change-password` |
| `newsletters.py` | Newsletter CRUD, `/run`, `/pause`, `/archive`, `/schedule/pause`, `/schedule/resume`, form-options, recipient import |
| `runs.py` | Read-only `/runs` list with filters and `/runs/{id}` detail (recipients, events) |
| `providers.py` | AI provider CRUD, model discovery, preset list, provider test endpoint |
| `api_keys.py` | Stored credentials for AI providers and Resend; encrypted at rest |
| `email_templates.py` | Email template CRUD and default-template selection |
| `audit.py` | Read-only `/audit/events` list with filters |
| `webhooks.py` | Resend webhook receiver (bounce / complaint suppression, delivered / opened / clicked events) |
| `public.py` | Unauthenticated endpoints — health check, unsubscribe link handler |

## For AI Agents

### Working In This Directory
- Every endpoint must call `require_authenticated_user(request, db)` at the top, except those deliberately registered in `public.py`.
- Audit every mutation via `create_audit_event(...)` before `db.commit()`.
- Use Pydantic request/response models from `app/schemas.py` — never return raw ORM objects.
- The send flow is single-step and lives in `newsletters.py::run_newsletter`. Do not add intermediate draft/preview/reconciliation endpoints.

### Testing Requirements
- Every endpoint must be covered by `backend/tests/test_<resource>.py` using FastAPI's `TestClient`.

### Common Patterns
- `APIRouter(prefix="/resource", tags=["resource"])` at the top of each module.
- `get_<resource>_or_404(db, id)` helper near the top for single-row lookups.
- `serialize_<resource>_detail(obj)` helper that returns a Pydantic `*Detail` model.

## Dependencies

### Internal
- `../auth.py` for session enforcement
- `../models.py`, `../schemas.py`, `../deps.py`
- `../ai_generation.py` and `../email_delivery.py` for the run path

### External
- `fastapi`, `sqlalchemy`, `pydantic`
