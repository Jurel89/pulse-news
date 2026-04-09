# Phase 3: AI Generation and Manual Delivery - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Add multi-provider draft generation, immutable run snapshots, and manual newsletter delivery through Resend. This phase should build on the verified newsletter, preview, and test-send foundations from Phases 1 and 2 rather than replacing them.

</domain>

<decisions>
## Implementation Decisions

### Provider abstraction
- **D-01:** Introduce one backend provider service for draft generation, with model/provider config read from each newsletter definition.
- **D-02:** Use LiteLLM as the provider abstraction when credentials are available, but keep a local fallback path for autonomous verification and development.
- **D-03:** Normalize provider errors into one operator-facing shape before they reach the UI.

### Run model
- **D-04:** Create immutable newsletter run records before generation or delivery happens.
- **D-05:** Snapshot subject, preheader, body, template, provider, model, trigger mode, and recipient list on every run.
- **D-06:** Keep manual runs and future scheduled runs on the same run lifecycle.

### Delivery
- **D-07:** Extend the existing test-send delivery boundary into a manual production send path rather than creating a second outbound transport layer.
- **D-08:** Manual delivery should target all active recipients on the newsletter and store per-recipient outcomes.

### UI flow
- **D-09:** Keep generation and manual-send actions close to the newsletter workflow, not buried in a future dashboard.
- **D-10:** Surface run results clearly enough that the operator can tell generation failures from delivery failures.

### the agent's Discretion
- Exact prompt shape passed into the generator
- Fallback generation behavior when no provider credentials are configured
- How much run detail is surfaced in Phase 3 UI before the dedicated dashboard phase

</decisions>

<specifics>
## Specific Ideas

- AI generation should populate the existing draft fields instead of introducing a parallel draft representation immediately.
- Manual delivery must reuse the same rendered subject/body previewed in Phase 2.
- Phase 3 should store enough run data that Phase 4 can focus on scheduling/dashboard presentation rather than reworking persistence.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product scope
- `.planning/PROJECT.md` — operator-first product constraints
- `.planning/REQUIREMENTS.md` — Phase 3 requirement mapping
- `.planning/ROADMAP.md` — Phase 3 goal and success criteria
- `.planning/STATE.md` — current focus after Phase 2 completion

### Prior phase outputs
- `.planning/phases/02-draft-workflow-and-template-system/02-01-SUMMARY.md` — draft content and recipient data shape
- `.planning/phases/02-draft-workflow-and-template-system/02-02-SUMMARY.md` — render and preview contract
- `.planning/phases/02-draft-workflow-and-template-system/02-03-SUMMARY.md` — delivery boundary and test-send contract
- `.planning/phases/02-draft-workflow-and-template-system/02-VERIFICATION.md` — verified Phase 2 proof points

### Research
- `.planning/research/STACK.md` — LiteLLM/provider guidance
- `.planning/research/ARCHITECTURE.md` — run-first orchestration and integration boundaries
- `.planning/research/PITFALLS.md` — duplicate-send, snapshot, and provider-leak pitfalls
- `.planning/research/SUMMARY.md` — recommended phase ordering rationale

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/email_templates.py` — render layer that manual sends must reuse
- `backend/app/email_delivery.py` — delivery service boundary already in place
- `backend/app/api/newsletters.py` — newsletter workflow endpoints and authenticated resource patterns
- `frontend/src/features/newsletters/` — newsletter editor/list/preview flow ready for generation and send actions

### Established Patterns
- Authenticated JSON API with frontend feature components and shared API client
- Newsletter data is the central object that later capabilities should enrich, not replace
- Delivery results already distinguish `resend` vs `local-preview` explicitly

### Integration Points
- AI generation should update newsletter draft fields and/or create run snapshots through the backend
- Manual send should plug into the existing delivery service and render service
- Run records must connect newsletters, recipients, generation state, and delivery state

</code_context>

<deferred>
## Deferred Ideas

- Recurring schedules and dashboard-heavy run exploration stay in Phase 4.
- Unsubscribe enforcement and delivery reconciliation stay in Phase 5.

</deferred>

---
*Phase: 03-ai-generation-and-manual-delivery*
*Context gathered: 2026-04-09*
