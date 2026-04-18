<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# dashboard

## Purpose
Operator landing view after login. Lists newsletter runs with filtering (newsletter, type, status, trigger mode, date range) and inline expansion for recipient outcomes and run events.

## Key Files
| File | Description |
|------|-------------|
| `RunDashboardPage.tsx` | Run list + filter bar + inline detail panel. Owns its own data fetching via `api.listRuns` and `api.getRunDetail` (detail is lazy-loaded on row expansion) |

## For AI Agents

### Working In This Directory
- Recipient outcome status is `"sent"` on successful Resend delivery; the webhook handler does not currently promote it to `"delivered"`. The success styling check accepts both strings — keep it that way until webhooks start mutating outcomes.
- The filter bar uses `useCallback` + `useEffect` to refetch runs whenever any filter changes. Don't debounce — the backend list is tiny.
- `initialRunId` prop allows deep-linking to a specific run from elsewhere in the app; auto-open is handled by a ref to avoid reopening on subsequent renders.

## Dependencies

### Internal
- `../../lib/api.ts`
- `../newsletters/newsletter-types.ts`
- `../../components/ui/ActionDropdown.tsx`
