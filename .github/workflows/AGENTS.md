<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# workflows

## Purpose
GitHub Actions CI configuration.

## Key Files
| File | Description |
|------|-------------|
| `ci.yml` | Five-job CI pipeline triggered on `push` to `main` and all PRs targeting `main`: `backend-lint`, `backend-test`, `frontend-build`, `frontend-typecheck`, `e2e` |

## For AI Agents

### Working In This Directory
- All five jobs must be green for a PR to merge. Keep them fast — the full pipeline is expected to finish in well under five minutes.
- The `e2e` job starts the full docker stack via `PORT=9876 make up`, waits for `/api/health`, installs Chromium, and runs `npx playwright test` with the default single worker. If you change the health path, the stack startup, or the Playwright baseURL, update this job too.
- Concurrency is configured to cancel in-progress runs for the same ref, so pushing a new commit aborts older jobs.

## Dependencies

### Internal
- `Makefile` → `make up` is called by the `e2e` job.
- `backend/pyproject.toml` + `frontend/package.json` — CI `pip install -e ".[dev]"` / `npm ci` off these manifests.

### External
- `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`
