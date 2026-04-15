<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# audit

## Purpose
Read-only audit log viewer. Every mutation endpoint in the backend writes an `AuditEvent` row via `create_audit_event()`; this page lists them with filters.

## Key Files
| File | Description |
|------|-------------|
| `AuditLogsPage.tsx` | Paginated audit event list with filters on actor / action / entity type |
| `audit-types.ts` | `AuditEventSummary`, filter payload types |

## For AI Agents

### Working In This Directory
- This page is read-only — do not add write actions. Audit events are produced by other endpoints, not authored here.
- `event.payload_json` is raw JSON; prefer rendering it as a collapsible `<pre>` rather than trying to parse every shape.

## Dependencies

### Internal
- `../../lib/api.ts`
