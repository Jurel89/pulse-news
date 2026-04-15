<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# auth

## Purpose
Unauthenticated entry point. Shows the bootstrap form on a fresh install (no operators yet) and the login form otherwise.

## Key Files
| File | Description |
|------|-------------|
| `LoginPage.tsx` | Dual-mode page — bootstrap when `session.initialized === false`, login when an operator already exists. Optional bootstrap-secret field gated by the backend `PULSE_NEWS_BOOTSTRAP_SECRET` env var |

## For AI Agents

### Working In This Directory
- The "create the first operator account" vs "log in to Pulse News" headings are load-bearing for operator clarity — change the copy carefully.
- Submission calls `onSubmit(email, password, bootstrapSecret?)` on the parent `App`, which in turn calls `api.bootstrap` or `api.login`.

## Dependencies

### Internal
- `../../lib/api.ts` (through the `onSubmit` handler in `App.tsx`)
