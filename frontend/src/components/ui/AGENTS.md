<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# ui

## Purpose
Low-level UI primitives. These components have no knowledge of newsletters / providers / api keys.

## Key Files
| File | Description |
|------|-------------|
| `ActionDropdown.tsx` | Portal-rendered contextual action menu triggered by a three-dot button; selectors `.action-dropdown-trigger` and `.action-dropdown-item` are used by e2e tests |
| `Dropdown.tsx` | Generic select-style dropdown used in form editors |

## For AI Agents

### Working In This Directory
- E2E tests rely on the `.action-dropdown-trigger` / `.action-dropdown-item` class names. Do not rename them without updating `frontend/tests/e2e/*.spec.ts`.
- `ActionDropdown` uses a React portal so it can escape overflow-clipped containers — preserve that pattern if editing.
- Items with `hidden: true` are filtered out; use that to hide actions conditionally rather than conditionally building the `actions` array.

## Dependencies

### External
- `react`, `react-dom` (for `createPortal`)
