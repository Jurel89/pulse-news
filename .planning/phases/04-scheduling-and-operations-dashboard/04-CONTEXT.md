# Phase 4: Scheduling and Operations Dashboard - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the product operationally useful for recurring sends with restart-safe scheduling and clear run visibility. Phase 4 should build on the Phase 3 run, render, and delivery contracts rather than reworking them.

</domain>

<decisions>
## Implementation Decisions

### Scheduling model
- **D-01:** Use APScheduler in-process with persistent SQLite-backed job storage and startup reconciliation.
- **D-02:** Keep scheduled execution on the same run-first delivery path as manual send.
- **D-03:** Add explicit schedule enable/disable control to newsletters rather than overloading generic newsletter status.

### Dashboard shape
- **D-04:** Use the existing dashboard view in the operator shell for run history and filters.
- **D-05:** Expose list and detail endpoints for runs rather than embedding run history into newsletter endpoints.
- **D-06:** Surface run status, trigger mode, provider/model, snapshots, recipient outcomes, and timestamps in the detail experience.

### the agent's Discretion
- Exact scheduler module shape
- Whether schedule reconciliation is triggered inline on newsletter saves or via a dedicated service helper

</decisions>

<specifics>
## Specific Ideas

- Scheduled sends must survive restarts without creating duplicate future jobs.
- Dashboarding should feel like an operations console, not a raw debug log.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product scope
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`

### Prior phase outputs
- `.planning/phases/03-ai-generation-and-manual-delivery/03-VERIFICATION.md`
- `.planning/phases/03-ai-generation-and-manual-delivery/03-03-SUMMARY.md`
- `.planning/phases/03-ai-generation-and-manual-delivery/03-04-SUMMARY.md`

### Research
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/PITFALLS.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/email_delivery.py` and `backend/app/email_templates.py` already define the shared send/render contract.
- `NewsletterRun` already stores snapshots and delivery outcomes.
- The frontend already has an operator dashboard tab and newsletter preview/send flows.

### Established Patterns
- Execution actions return normalized status/mode/message envelopes.
- The backend is the source of truth for newsletter execution and history.

### Integration Points
- Scheduler should call the same send helper as manual delivery.
- Dashboard should read `NewsletterRun` records directly.

</code_context>

<deferred>
## Deferred Ideas

- Compliance suppression and reconciliation UI stay in Phase 5.

</deferred>

---
*Phase: 04-scheduling-and-operations-dashboard*
*Context gathered: 2026-04-09*
