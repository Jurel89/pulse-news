<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# frontend

## Purpose
Operator-facing single-page React/TypeScript UI. It talks exclusively to the backend at `/api/*` via `src/lib/api.ts`. In production it is built with Vite into a static bundle and served by the same container as the backend; locally it can also run under `vite dev` with a backend proxy.

## Key Files
| File | Description |
|------|-------------|
| `package.json` | Dependencies and `build` / `dev` / `preview` scripts |
| `vite.config.ts` | Vite build + dev-server proxy configuration for `/api` |
| `tsconfig.json` / `tsconfig.app.json` | TypeScript project references |
| `playwright.config.ts` | E2E config (base URL, headless chromium, 60s test timeout) |
| `index.html` | Vite entrypoint HTML |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `src/` | Application source (App shell, features, components, API client) — see `src/AGENTS.md` |
| `tests/` | Playwright E2E tests — see `tests/AGENTS.md` |

## For AI Agents

### Working In This Directory
- Node 20, TypeScript strict mode, React 19 functional components with hooks.
- No CSS-in-JS; styling lives in `src/styles.css`. Component-level style is via class names that are already defined there.
- Don't introduce a new state-management library — local state + prop drilling from `App.tsx` is intentional for a product this small.

### Testing Requirements
- `npx tsc --noEmit` must be clean.
- `npm run build` must succeed.
- `npx playwright test --workers=1` must pass against a running backend (see `tests/e2e/AGENTS.md`).

### Common Patterns
- Feature modules live in `src/features/<domain>/` and expose a page component plus a `<domain>-types.ts` with `Summary` / `Detail` / `Input` shapes mirrored to backend Pydantic schemas.
- All HTTP calls go through the `api` export of `src/lib/api.ts` — never `fetch` directly from a component.

## Dependencies

### External
- `react`, `react-dom` — UI runtime
- `vite`, `@vitejs/plugin-react` — build / dev server
- `typescript` — type system
- `@playwright/test` — E2E testing
