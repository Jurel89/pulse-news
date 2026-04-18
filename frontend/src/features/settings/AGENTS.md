<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# settings

## Purpose
Per-operator account controls — currently change-password and logout. Global/system settings live in the backend `SystemSettings` model and are not operator-editable from the UI.

## Key Files
| File | Description |
|------|-------------|
| `AccountPage.tsx` | Shows the current user email and exposes change-password + logout actions |

## For AI Agents

### Working In This Directory
- Do not turn this into a dumping ground for feature flags or system-wide knobs. Those belong on `SystemSettings` in the backend and, if they must be user-editable, on their own dedicated page.
- Password validation on the backend requires `min_length=8`; mirror that constraint in the client-side form if you add one.

## Dependencies

### Internal
- `../../lib/api.ts` (via `App.tsx` handlers)
