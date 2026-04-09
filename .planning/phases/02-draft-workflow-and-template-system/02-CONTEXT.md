# Phase 2: Draft Workflow and Template System - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Let the operator prepare newsletters safely through recipients, themed templates, previews, and test sends before live delivery. This phase builds on the Phase 1 newsletter CRUD foundation and does not yet introduce AI draft generation or recurring schedules.

</domain>

<decisions>
## Implementation Decisions

### Recipient model
- **D-01:** Model recipients directly under a newsletter for v1 instead of introducing reusable audience segments yet.
- **D-02:** Support both manual entry and CSV import in the UI.
- **D-03:** Keep recipient rows ready for later compliance work by including `is_active` and `unsubscribe_token` foundations even if unsubscribe handling lands in Phase 5.

### Draft content and templates
- **D-04:** Add editable draft content fields to the newsletter definition now so preview and test send have real material to render before AI generation exists.
- **D-05:** Implement a small curated template family system in the backend render layer rather than a drag-and-drop or freeform HTML builder.
- **D-06:** Treat HTML preview and plain-text preview as first-class outputs of the same render service.

### Test send behavior
- **D-07:** Use the same outbound email service boundary for test sends that later manual sends will use.
- **D-08:** When Resend credentials are unavailable in local/dev verification, allow a local fallback path that records the rendered payload without pretending a live send occurred.
- **D-09:** Test sends are operator-triggered and target one address at a time from the UI.

### UI flow
- **D-10:** Keep draft preparation inside the existing newsletter editor workflow rather than making previews/test sends a separate application area.
- **D-11:** Optimize Phase 2 UI for quick editorial iteration: edit, preview, tweak, test send.

### the agent's Discretion
- Exact CSV import ergonomics
- Which template families ship first, as long as they are visually distinct
- Whether template rendering lives in a dedicated service module or a template package

</decisions>

<specifics>
## Specific Ideas

- Distinct template aesthetics matter more than having many templates.
- The operator should be able to see both HTML and plain-text versions before sending.
- Phase 2 should create reusable building blocks for Phase 3 delivery instead of a throwaway preview system.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product scope
- `.planning/PROJECT.md` — product boundary and operator-first constraints
- `.planning/REQUIREMENTS.md` — Phase 2 requirement mapping
- `.planning/ROADMAP.md` — Phase 2 goal and success criteria
- `.planning/STATE.md` — current phase position after Phase 1 completion

### Prior phase outputs
- `.planning/phases/01-foundation-and-secure-control-plane/01-01-SUMMARY.md` — shell and container baseline
- `.planning/phases/01-foundation-and-secure-control-plane/01-02-SUMMARY.md` — auth/session patterns
- `.planning/phases/01-foundation-and-secure-control-plane/01-03-SUMMARY.md` — newsletter CRUD patterns
- `.planning/phases/01-foundation-and-secure-control-plane/01-VERIFICATION.md` — verified Phase 1 proof points

### Research
- `.planning/research/FEATURES.md` — operator feature priorities and anti-features
- `.planning/research/ARCHITECTURE.md` — service boundaries for rendering and delivery
- `.planning/research/PITFALLS.md` — preview/test-send and auditability pitfalls to avoid

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/api/newsletters.py` — authenticated newsletter resource foundation
- `frontend/src/features/newsletters/` — newsletter management UI structure ready for extension
- `frontend/src/lib/api.ts` — shared authenticated frontend API client

### Established Patterns
- The backend is the source of truth for authenticated state and core newsletter data.
- The frontend uses focused feature components driven by the shared API client.
- The one-container packaging path is already verified and should be extended, not replaced.

### Integration Points
- Recipient CRUD attaches to the existing newsletter entity.
- Template rendering and test send should plug into the existing backend service boundary and frontend editor flow.

</code_context>

<deferred>
## Deferred Ideas

- AI-generated drafts stay in Phase 3.
- Recurring schedules and operational dashboards stay in Phase 4.
- Unsubscribe enforcement and delivery reconciliation stay in Phase 5.

</deferred>

---
*Phase: 02-draft-workflow-and-template-system*
*Context gathered: 2026-04-09*
