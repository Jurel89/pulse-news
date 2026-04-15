<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# e2e

## Purpose
Playwright smoke + critical-path tests. They run against the real bundled app served by the backend container on `http://127.0.0.1:9876` — there is no mock server.

## Key Files
| File | Description |
|------|-------------|
| `bootstrap-and-dashboard.spec.ts` | Bootstrap/login flow, provider dropdown action cycle, api-key activate/deactivate toggle. Tests seed their own provider + api key via API before interacting with the UI |
| `create-newsletter-ui.spec.ts` | Newsletters nav surfaces the "New Newsletter" button |

## For AI Agents

### Working In This Directory
- **Run with `--workers=1`** locally to match CI. Multiple workers racing the first-run `bootstrap` endpoint will cause spurious 500s.
- Always seed test fixtures via `fetch('/api/...', { credentials: 'include' })` inside `page.evaluate`. Do not assume the backend has any providers, API keys, or newsletters on a fresh bootstrap.
- Use unique suffixes (`Date.now()`-based) in names to keep tests idempotent across runs that share a persistent DB.
- Scope selectors to the card/row created by the test (e.g. `article.newsletter-card:hasText(<name>)`) rather than `.first()` against the global list — otherwise adding a second test will break the first.

### Testing Requirements
- Start the stack first: `PORT=9876 make up`, wait for `/api/health`, then `npx playwright install chromium` once, then `npx playwright test --workers=1`.

## Dependencies

### External
- `@playwright/test`
