<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# src

## Purpose
Frontend application source. `App.tsx` is the shell — it owns top-level state (session, newsletters, templates, providers, api keys), the navigation pill bar, and dispatches to feature pages based on the active view.

## Key Files
| File | Description |
|------|-------------|
| `main.tsx` | Vite entrypoint — mounts `<App />` into `#root` |
| `App.tsx` | Top-level shell: session bootstrap, nav pills, view routing, CRUD handlers for newsletters/templates/providers/api-keys |
| `styles.css` | All application styling (no CSS modules or CSS-in-JS) |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `components/` | Reusable UI primitives (`ActionDropdown`, `Dropdown`) — see `components/AGENTS.md` |
| `features/` | Feature modules — one folder per product domain — see `features/AGENTS.md` |
| `lib/` | Cross-cutting utilities (API client, session helpers) — see `lib/AGENTS.md` |

## For AI Agents

### Working In This Directory
- `App.tsx` is deliberately long and procedural. Do not prematurely extract a router, state manager, or context provider — the product is small enough that `useState` + prop drilling is the right tool.
- New feature pages belong under `features/<domain>/`. Wire them into the `ActiveView` union and the `navItems` memo in `App.tsx`.
- All network calls go through `lib/api.ts`. Components should never `fetch('/api/...')` directly.

### Common Patterns
- Loading state is per-feature (`newslettersLoading`, `templatesLoading`, ...). Top-level `busy` is reserved for mutation handlers.
- Errors are surfaced via the shared `error` string and dismissable banners; routes call `setError(null)` on successful operations.

## Dependencies

### External
- `react`, `react-dom`
