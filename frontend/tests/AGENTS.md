<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# tests

## Purpose
Playwright end-to-end tests. The suite exercises the real bundled app served by the backend container on port 9876; there is no mock server.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `e2e/` | Test specs — see `e2e/AGENTS.md` |

## For AI Agents

### Working In This Directory
- Run with `npx playwright test --workers=1` to match CI (multi-worker races bootstrap).
- The default baseURL `http://127.0.0.1:9876` expects `PORT=9876 make up` to have started the stack.

## Dependencies

### External
- `@playwright/test`
