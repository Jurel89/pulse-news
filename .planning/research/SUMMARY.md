# Project Research Summary

**Project:** Pulse News
**Domain:** Self-hosted AI-assisted newsletter operations app
**Researched:** 2026-04-09
**Confidence:** HIGH

## Executive Summary

Pulse News is best treated as an operator-first content operations product, not a public newsletter SaaS or marketing site. The shortest sound path is a single-container application with a Python backend that owns scheduling, provider abstraction, sending, and auditability, plus a React admin UI for the responsive workflow and dashboards the user asked for.

The main stack decision is not “Python or React?” but “where do provider routing and sending boundaries live?” Research points to keeping provider logic centralized behind LiteLLM in the backend and treating Resend as the outbound delivery system of record. React Email is a good fit for reusable visual newsletter templates without turning v1 into an HTML-builder project.

The main risks are duplicate sends, weak single-user auth, schedule drift after restart, and losing historical content provenance. The roadmap should therefore front-load auth, domain boundaries, immutable run records, and scheduler integrity before polishing template variety or advanced provider routing.

## Key Findings

### Recommended Stack

Keep the user’s Python + React instinct, but narrow it into a concrete shape: FastAPI for the backend API and orchestration layer, React + Vite for the operator UI, SQLite + SQLAlchemy for v1 persistence, APScheduler for in-process recurring jobs, LiteLLM for provider breadth, and React Email for HTML/plain-text template rendering.

**Core technologies:**
- Python: backend runtime for AI orchestration and integrations
- FastAPI: API and service host for auth, runs, scheduling, and integrations
- React + Vite: responsive operator dashboard and management UI
- SQLite + SQLAlchemy: single-container persistence baseline
- APScheduler: persistent recurring-job coordinator
- LiteLLM: multi-provider generation interface
- React Email: reusable themed email template rendering

### Expected Features

The table stakes are operational: secure login, newsletter CRUD, recipients, schedules, manual runs, previews/test sends, and trustworthy run history. The differentiators are newsletter-specific prompt behavior, multi-provider generation, template families, and immutable generation/send snapshots.

**Must have (table stakes):**
- Secure single-user authentication
- Newsletter CRUD with prompt, template, recipients, and schedule settings
- Manual run plus recurring schedule support
- Draft preview/test send workflow
- Delivery dashboard with run status, recipient list, content snapshots, and errors

**Should have (competitive):**
- Newsletter-specific provider/model policies
- Multi-provider routing/fallbacks
- Template family/theming system
- Strong per-run observability

**Defer (v2+):**
- Public subscribe site
- Multi-user roles
- Rich drag-and-drop builder
- Deep engagement analytics

### Architecture Approach

Use one FastAPI application as the backend shell, but keep clean internal service boundaries: auth/session, newsletter domain, scheduler coordinator, run orchestrator, provider service, delivery service, and audit store. The UI stays separate at the code layer but bundles into the same container. Manual and scheduled runs must go through the same persisted execution path.

**Major components:**
1. Admin UI — operator workflows, previews, dashboards
2. Domain services — newsletters, recipients, templates, runs
3. Scheduler/orchestrator — manual and recurring execution
4. Provider service — LiteLLM-backed content generation
5. Delivery service — Resend-backed outbound send and status reconciliation
6. Audit store — immutable run/content/error history

### Critical Pitfalls

1. **Duplicate sends** — prevent with persisted run IDs and idempotent delivery logic
2. **Missing content snapshots** — persist immutable per-run payloads, not just current config
3. **Provider leakage** — keep provider-specific logic inside an integration boundary
4. **Resend MCP overreach** — use MCP as an edge/tool integration, not the app’s core transport contract
5. **Scheduler restart drift** — use persistent jobs, explicit IDs, and startup reconciliation
6. **Weak single-user auth** — treat “single user” as simpler UX, not weaker security

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation and Secure Control Plane
**Rationale:** Auth, persistence, and service boundaries must exist before scheduling or sending.
**Delivers:** Backend shell, frontend shell, single-user auth, core newsletter data model
**Addresses:** Authentication, newsletter CRUD foundation
**Avoids:** Weak auth and provider leakage

### Phase 2: Execution Pipeline and Delivery History
**Rationale:** The product is not useful until manual runs, immutable run records, and Resend-backed sends work.
**Delivers:** Run orchestration, content generation, template rendering, Resend send pipeline, audit log model
**Uses:** LiteLLM, React Email, Resend integration
**Implements:** Provider service, delivery service, run snapshot architecture

### Phase 3: Scheduling and Operational Dashboard
**Rationale:** Recurring schedules and operator visibility turn the send pipeline into a real operations product.
**Delivers:** APScheduler-backed recurring jobs, schedule reconciliation, dashboard views, run detail pages
**Uses:** Persistent job store and run-history queries
**Implements:** Scheduler coordinator and dashboard UI

### Phase 4: Template Library and Provider Policy Refinement
**Rationale:** Once sending is stable, the next leverage point is better editorial control and template reuse.
**Delivers:** Template families, theme controls, provider/model policies, fallback behavior
**Uses:** Existing email and provider service boundaries
**Implements:** Product differentiation without reopening core architecture

### Phase Ordering Rationale

- Auth and domain boundaries come before integrations so secrets, models, and permissions are not retrofitted.
- Sending comes before scheduling because recurring jobs should reuse a trusted manual-run path.
- Dashboard work belongs with scheduling because operators need visibility into automated runs the moment they exist.
- Template and provider refinements come later because they build on already-safe execution paths.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Delivery transport details if the user insists on MCP-native sending rather than API-backed sending
- **Phase 4:** Provider routing/fallback policy design once real providers/models are selected

Phases with standard patterns (skip research-phase):
- **Phase 1:** Auth, CRUD shell, and service boundaries are well understood
- **Phase 3:** APScheduler-backed schedule persistence and dashboard surfacing are standard once the run model exists

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core choices grounded in official docs and current registry versions |
| Features | HIGH | Product shape is narrow and operator-focused |
| Architecture | HIGH | Single-container monolith with clear service boundaries fits the constraints well |
| Pitfalls | HIGH | Main failure modes are well understood for scheduler/send/audit systems |

**Overall confidence:** HIGH

### Gaps to Address

- Confirm whether the user wants Resend MCP as an operator-facing agent tool, a backend transport detail, or both
- Decide whether v1 recipient management is manual/import-based only or needs segmentation beyond stored lists
- Decide whether SQLite remains acceptable after estimating typical newsletter size and send frequency

## Sources

### Primary (HIGH confidence)
- FastAPI docs: https://fastapi.tiangolo.com/tutorial/background-tasks/
- APScheduler docs: https://apscheduler.readthedocs.io/en/stable/userguide.html
- LiteLLM docs: https://docs.litellm.ai/
- LiteLLM site: https://www.litellm.ai/
- Resend MCP docs: https://resend.com/mcp
- Resend API docs: https://resend.com/docs/api-reference/introduction
- React Email docs: https://react.email/docs/utilities/render
- Django overview: https://www.djangoproject.com/start/overview/
- Django auth docs: https://docs.djangoproject.com/en/5.0/topics/auth/default/
- Next.js docs: https://nextjs.org/docs/app/getting-started/installation
- OpenCode README: https://github.com/opencode-ai/opencode

### Secondary (MEDIUM confidence)
- Package registry metadata from `pip index` and `npm view` for current version baselines

### Tertiary (LOW confidence)
- None

---
*Research completed: 2026-04-09*
*Ready for roadmap: yes*
