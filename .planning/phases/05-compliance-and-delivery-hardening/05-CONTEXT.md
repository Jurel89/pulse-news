# Phase 5: Compliance and Delivery Hardening - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Enforce recipient compliance and improve delivery-state trust for ongoing production use. This phase should add unsubscribe/suppression behavior and reconciliation events on top of the Phase 4 dashboard and Phase 3 delivery model.

</domain>

<decisions>
## Implementation Decisions

### Compliance
- **D-01:** Add an explicit delivery topic/unsubscribe scope to each newsletter.
- **D-02:** Use recipient unsubscribe tokens plus stored suppression state so future sends exclude suppressed recipients automatically.
- **D-03:** Expose a simple public unsubscribe endpoint suitable for v1 self-hosted use.

### Reconciliation
- **D-04:** Add run-level delivery reconciliation events rather than mutating away existing send outcomes.
- **D-05:** Use Resend retrieve-email when provider IDs exist and fall back to explicit local/simulated reconciliation messages otherwise.

### the agent's Discretion
- Exact event model shape
- Whether unsubscribe UI stays minimal or includes extra operator management polish

</decisions>

<specifics>
## Specific Ideas

- The operator should be able to trust that suppressed recipients stay excluded.
- Reconciliation should add history, not overwrite it.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product scope
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`

### Prior phase outputs
- `.planning/phases/04-scheduling-and-operations-dashboard/04-CONTEXT.md`
- `.planning/phases/03-ai-generation-and-manual-delivery/03-VERIFICATION.md`

### Research and external contracts
- `.planning/research/PITFALLS.md`
- `https://resend.com/docs/api-reference/emails/retrieve-email` — retrieve sent email status
- `https://resend.com/docs/dashboard/emails/idempotency-keys` — send idempotency considerations

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `NewsletterRecipient` already has `is_active` and `unsubscribe_token`.
- Delivery services already distinguish fallback vs live send modes.
- `NewsletterRun` already stores delivery outcomes for each run.

### Established Patterns
- Run results are normalized and flow through dedicated API schemas.
- Dashboard/run work should read execution history from the run model, not recompute it.

### Integration Points
- Suppression should affect the existing send path directly.
- Reconciliation events should extend run detail APIs and dashboard detail UI.

</code_context>

<deferred>
## Deferred Ideas

- Team workflows and richer analytics remain out of scope for v1.

</deferred>

---
*Phase: 05-compliance-and-delivery-hardening*
*Context gathered: 2026-04-09*
