<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# pulse-news

## Purpose
Simple AI newsletter platform. An operator configures an AI provider and a Resend API key, creates a newsletter with a prompt (e.g. "give me the last AI trends this week"), and runs it. The AI generates the subject / preheader / body, it is rendered into an HTML email template, and Resend delivers it to the recipient list. That is the whole product.

## Key Files
| File | Description |
|------|-------------|
| `README.md` | Project overview, setup, and usage |
| `Makefile` | `build` / `up` / `down` / `logs` / `shell` targets wrapping docker compose |
| `Dockerfile` | Single-image build (Python + built frontend + migrations + uvicorn) |
| `docker-compose.yml` | Local and CI service definition for the `pulse-news` container |
| `alembic.ini` | Alembic config for DB migrations |
| `.env.example` | Template for required environment variables |
| `LICENSE` | Project license |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `backend/` | FastAPI backend (Python 3.13, SQLAlchemy, Alembic) — see `backend/AGENTS.md` |
| `frontend/` | React/TypeScript operator UI (Vite) — see `frontend/AGENTS.md` |
| `alembic/` | DB migration scripts — see `alembic/AGENTS.md` |
| `docs/` | Product/design assets (SVGs) — see `docs/AGENTS.md` |
| `.github/` | GitHub Actions CI configuration — see `.github/AGENTS.md` |

## For AI Agents

### Working In This Directory
- The product is intentionally small. Do NOT reintroduce draft/revision workflows, generation/delivery profiles, simulated operation modes, test-send endpoints, reconciliation actions, or multi-step "send" flows. A previous simplification PR removed all of these; they should stay removed.
- The core flow is `POST /api/newsletters/{id}/run` → `generate_newsletter_content` → render template → `execute_newsletter_send` via Resend. A generation failure is a hard stop (HTTP 422), not a retry or draft.
- Manual "Run Now" always creates a fresh send; there is no deduplication for manual runs.
- Prefer editing existing code over adding abstractions. A bug fix should not bring cleanup scope with it.

### Testing Requirements
- Backend: `cd backend && pytest` (see `backend/tests/AGENTS.md`)
- Frontend: `cd frontend && npx tsc --noEmit && npm run build`
- E2E: start the stack with `PORT=9876 make up`, wait for `/api/health`, then `cd frontend && npx playwright test --workers=1`
- All five CI jobs (`backend-lint`, `backend-test`, `frontend-build`, `frontend-typecheck`, `e2e`) must be green before merging.

### Common Patterns
- Backend uses FastAPI routers per resource, SQLAlchemy 2.x models in `backend/app/models.py`, and Pydantic v2 schemas in `backend/app/schemas.py`.
- Frontend uses feature-folder layout under `frontend/src/features/<domain>/` with domain-specific `*-types.ts` files and a thin API wrapper in `frontend/src/lib/api.ts`.
- E2E tests seed their own fixtures via API before touching the UI — never assume pre-existing data on fresh bootstrap.

## Dependencies

### External
- **FastAPI** + **uvicorn** — HTTP framework
- **SQLAlchemy** + **Alembic** — ORM and migrations (SQLite in dev, volume-mounted)
- **Pydantic v2** — request/response validation
- **APScheduler** — recurring newsletter schedules
- **litellm** — AI provider abstraction (OpenAI / Anthropic / Gemini / OpenRouter / zai / Kimi)
- **Resend** (REST) — email delivery
- **React 18** + **TypeScript** + **Vite** — frontend
- **Playwright** — E2E testing
