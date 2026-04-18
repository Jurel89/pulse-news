<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# alembic

## Purpose
Alembic DB migration scaffolding. The app auto-runs `alembic upgrade head` on startup (see `backend/app/main.py`), so every schema change must have a migration here.

## Key Files
| File | Description |
|------|-------------|
| `env.py` | Alembic environment — wires SQLAlchemy metadata into Alembic's migration runner |
| `script.py.mako` | Template used when generating new revisions |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `versions/` | Individual revision scripts — see `versions/AGENTS.md` |

## For AI Agents

### Working In This Directory
- Generate new revisions with `cd backend && alembic revision -m "<short description>"` (config is in the repo root `alembic.ini`).
- Migrations must be idempotent — the app targets SQLite and runs `alembic upgrade head` on every startup, including fresh installs.
- Never edit an already-released migration (anything that has landed on `main`). Add a new one instead.

### Testing Requirements
- `backend/tests/test_database_migrations.py` verifies the migration chain can build a fresh schema end-to-end.

## Dependencies

### Internal
- `backend/app/models.py` — the SQLAlchemy metadata source of truth referenced by `env.py`.

### External
- `alembic`, `sqlalchemy`
