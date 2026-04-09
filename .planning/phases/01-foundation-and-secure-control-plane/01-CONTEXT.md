# Phase 1: Foundation and Secure Control Plane - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a protected single-user application shell with durable core data models for newsletters and account management. This phase establishes the backend/frontend baseline, secure operator access, and newsletter CRUD without yet implementing AI draft generation, recurring scheduling, or Resend-backed delivery.

</domain>

<decisions>
## Implementation Decisions

### Stack shape
- **D-01:** Use a FastAPI backend and React + Vite frontend, packaged into one Docker image with the backend serving the built frontend assets in production.
- **D-02:** Keep a monorepo split by responsibility (`backend/`, `frontend/`, `.planning/`) rather than separate deployables.
- **D-03:** Expose a JSON API under `/api/*` and keep the frontend as a SPA for operator workflows.

### Authentication model
- **D-04:** Use a single local operator account with first-run bootstrap, email/password login, logout, and password-change flows.
- **D-05:** Protect admin routes with a secure signed session cookie instead of HTTP basic auth.
- **D-06:** Lock bootstrap after the first account is created so account creation is not a standing public action.

### Data foundation
- **D-07:** Use SQLite for the initial persistent store because the product is explicitly single-user and single-container.
- **D-08:** Persist newsletter definitions with prompt, provider/model config, template choice, recipients placeholder, and schedule settings even if some later-phase fields are not fully used yet.
- **D-09:** Preserve soft operational history fields now where they help later phases, but defer run/delivery event models to the execution phases that actually use them.

### UI baseline
- **D-10:** Build a responsive admin shell with a login page, dashboard shell, newsletter list view, newsletter editor form, and account/settings area.
- **D-11:** Prefer a clean operational UI over marketing-style presentation.

### the agent's Discretion
- Exact folder naming inside `backend/app/` and `frontend/src/`
- Styling system and component organization
- Whether to use SQLAlchemy models directly or thin repository helpers in this phase

</decisions>

<specifics>
## Specific Ideas

- The app should feel like an operations console, not a public product website.
- The single-container requirement matters more than maximal framework purity.
- Resend MCP should not force awkward architecture in this phase; Phase 1 only needs foundations for later send flows.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product scope
- `.planning/PROJECT.md` — product boundary, constraints, and core value
- `.planning/REQUIREMENTS.md` — v1 requirement set and phase traceability
- `.planning/ROADMAP.md` — Phase 1 goal, requirements, and success criteria

### Research
- `.planning/research/STACK.md` — stack recommendation and constraints
- `.planning/research/ARCHITECTURE.md` — service boundaries and single-container architecture
- `.planning/research/PITFALLS.md` — auth, provider-boundary, and scheduler pitfalls to avoid
- `.planning/research/SUMMARY.md` — roadmap-level synthesis and ordering rationale

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — repository is greenfield.

### Established Patterns
- Planning artifacts already assume phase-based execution, Lore commits, and one-container deployment.

### Integration Points
- New application code will define the initial integration points. Backend static serving and frontend API consumption should be established here so later phases can extend them instead of replacing them.

</code_context>

<deferred>
## Deferred Ideas

- AI generation and provider routing belong to Phase 3.
- Recurring scheduling and run history dashboards belong to Phase 4.
- Unsubscribe/topic enforcement and delivery reconciliation belong to Phase 5.

</deferred>

---
*Phase: 01-foundation-and-secure-control-plane*
*Context gathered: 2026-04-09*
