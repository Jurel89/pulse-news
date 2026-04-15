<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# components

## Purpose
Cross-cutting UI primitives shared between feature pages. Domain-specific components live under `src/features/<domain>/` instead.

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `ui/` | Headless UI primitives (`ActionDropdown`, `Dropdown`) — see `ui/AGENTS.md` |

## For AI Agents

### Working In This Directory
- A component belongs here only if it is (or would be) reused by two or more features. Otherwise, keep it inside the feature folder.
- Keep primitives unopinionated — styling via `className` props, not hard-coded colors.
