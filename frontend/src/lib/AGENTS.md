<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# lib

## Purpose
Cross-cutting utilities shared across features.

## Key Files
| File | Description |
|------|-------------|
| `api.ts` | Single HTTP client facade. Exports `api` with typed methods for every backend endpoint (auth, newsletters, templates, providers, api keys, runs, audit, form options). All network I/O funnels through here |
| `session.ts` | `SessionState` type, `initialSessionState`, and `asLoadedSession()` helper for normalizing the `/api/auth/session` response |

## For AI Agents

### Working In This Directory
- New backend endpoints get a new method on `api` here — components must not `fetch('/api/...')` directly.
- All requests use `credentials: 'include'` so the session cookie is sent.
- Errors surface as thrown `Error` objects whose `.message` is the backend `detail`. Do not log response bodies to the console from this file — let the calling component decide what to surface.
- Keep method names aligned with the backend route path (e.g. `api.runNewsletter(id)` → `POST /newsletters/{id}/run`).

## Dependencies

### Internal
- Types imported from `../features/<domain>/<domain>-types.ts`
