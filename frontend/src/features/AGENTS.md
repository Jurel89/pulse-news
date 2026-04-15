<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# features

## Purpose
Feature modules — one folder per product domain. Each folder contains its page components and a `*-types.ts` with the TypeScript shapes that mirror the backend's Pydantic Summary / Detail / Input schemas.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `auth/` | Login / bootstrap page — see `auth/AGENTS.md` |
| `dashboard/` | Run dashboard (list + detail of past runs) — see `dashboard/AGENTS.md` |
| `newsletters/` | Newsletter list + editor — see `newsletters/AGENTS.md` |
| `templates/` | Email template list + editor — see `templates/AGENTS.md` |
| `providers/` | AI provider list + editor — see `providers/AGENTS.md` |
| `api-keys/` | API key (AI + Resend) list + editor — see `api-keys/AGENTS.md` |
| `audit/` | Audit log viewer — see `audit/AGENTS.md` |
| `settings/` | Account / change-password page — see `settings/AGENTS.md` |

## For AI Agents

### Working In This Directory
- A feature folder should export its page component(s) and a `<domain>-types.ts` — nothing else. Hooks specific to a feature can live alongside them; cross-cutting ones go to `../lib/`.
- When adding a feature, wire the page into `src/App.tsx` by (1) extending the `ActiveView` union, (2) adding a nav entry in `navItems`, (3) adding a `case` in `renderContent()`, and (4) adding load/save handlers.

### Common Patterns
- Pages are controlled components: they receive data + callbacks from `App.tsx` and do not own mutation logic.
- Editors are sibling components in the same folder, named `<Domain>Editor`.
