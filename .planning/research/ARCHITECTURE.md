# Architecture Research

**Domain:** Self-hosted AI-assisted newsletter operations app
**Researched:** 2026-04-09
**Confidence:** HIGH

## Standard Architecture

### System Overview

```text
┌──────────────────────────────────────────────────────────────┐
│                        Operator UI                            │
├──────────────────────────────────────────────────────────────┤
│  React Admin  │  Template Preview  │  Runs Dashboard         │
└───────────────┬─────────────────────┬─────────────────────────┘
                │                     │
┌───────────────┴─────────────────────┴─────────────────────────┐
│                     FastAPI Application                       │
├──────────────────────────────────────────────────────────────┤
│  Auth/Session  │  Newsletter API  │  Run Orchestrator        │
│  Recipient API │  Template Service │  Scheduler Coordinator   │
│  Audit API     │  Provider Service │  Delivery Service        │
└───────────────┬─────────────────────┬─────────────────────────┘
                │                     │
┌───────────────┴───────────────┐   ┌─┴─────────────────────────┐
│         Persistence           │   │       External Systems     │
├───────────────────────────────┤   ├────────────────────────────┤
│ SQLite app data              │   │ LiteLLM / provider APIs    │
│ SQLite/SQLAlchemy job store  │   │ Resend API / MCP edge      │
│ Run logs + content snapshots │   │ Optional webhooks/events   │
└───────────────────────────────┘   └────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Admin UI | Operator workflows for CRUD, runs, schedules, previews, and audit review | React app bundled and served by the backend container |
| Auth/session layer | Protect the single-user admin surface | Cookie-based session auth with secure password hashing and bootstrap flow |
| Newsletter domain service | Own newsletter definitions, templates, prompts, recipient references, and schedule config | FastAPI service layer over SQLAlchemy models |
| Run orchestrator | Execute manual or scheduled runs safely and idempotently | Application service that creates a run record before generation/sending |
| Scheduler coordinator | Trigger recurring runs and reconcile schedules after restart | APScheduler with persistent SQLAlchemy job store |
| Provider service | Generate content through model providers behind one internal interface | LiteLLM-backed adapter plus internal prompt/render policies |
| Delivery service | Send, retry, and record outbound email outcomes | Resend transport boundary with logging and webhook/event reconciliation |
| Audit/log store | Preserve content snapshots and operational history | Relational tables for runs, events, recipients, and errors |

## Recommended Project Structure

```text
src/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers and request/response schemas
│   │   ├── auth/           # Login, session, password bootstrap/reset
│   │   ├── domain/         # Newsletters, templates, recipients, runs
│   │   ├── services/       # Generation, delivery, scheduling, logging
│   │   ├── integrations/   # LiteLLM, Resend, optional MCP edge adapters
│   │   ├── db/             # Models, migrations, repositories
│   │   └── main.py         # App startup, scheduler bootstrap, static serving
├── frontend/
│   └── src/
│       ├── routes/         # Dashboard and admin routes
│       ├── features/       # Newsletter, runs, recipients, auth UI slices
│       ├── components/     # Shared UI building blocks
│       └── lib/            # API client, form helpers, responsive utilities
└── emails/
    ├── templates/          # React Email template families
    └── themes/             # Shared branding tokens and content blocks
```

### Structure Rationale

- **`backend/app/domain/`:** protects business rules from framework-specific details.
- **`backend/app/services/`:** keeps generation, scheduling, and sending orchestration separate from CRUD routes.
- **`backend/app/integrations/`:** prevents LiteLLM and Resend details from leaking across the codebase.
- **`frontend/src/features/`:** fits a dashboard/admin product better than route-only organization.
- **`emails/`:** isolates renderable email templates from the operator UI.

## Architectural Patterns

### Pattern 1: Run-first orchestration

**What:** Create a persisted run record before calling an LLM or send provider.
**When to use:** Always, for manual and scheduled sends.
**Trade-offs:** Slightly more persistence work up front, but much better auditability and recovery.

### Pattern 2: Integration boundary adapters

**What:** Keep LiteLLM and Resend behind narrow internal service interfaces.
**When to use:** From the first implementation phase.
**Trade-offs:** A little more abstraction early, but materially less vendor leakage later.

### Pattern 3: Immutable content snapshots

**What:** Store the generated subject/body/plain-text/template/provider metadata used for each run.
**When to use:** Every successful or failed generation/send attempt.
**Trade-offs:** More storage, but necessary for dashboard credibility and debugging.

## Data Flow

### Request Flow

```text
[Operator action]
    ↓
[React UI] → [FastAPI route] → [Domain service] → [SQLite]
    ↓             ↓                 ↓                 ↓
[Updated UI] ← [API response] ← [Run result/log] ← [Stored state]
```

### State Management

```text
[Server state]
    ↓
[UI query cache] ←→ [Forms / mutations] → [API routes] → [Domain services]
```

### Key Data Flows

1. **Newsletter configuration flow:** operator edits newsletter settings → backend validates/persists prompt/template/provider/schedule → scheduler reconciles jobs.
2. **Manual run flow:** operator clicks run → backend creates run record → provider service generates content → template renderer produces HTML/plain text → delivery service sends through Resend → dashboard updates.
3. **Scheduled run flow:** APScheduler fires persisted job → run orchestrator executes same pipeline as manual run → logs and statuses are written even if no UI session is open.
4. **History/dashboard flow:** backend serves immutable run snapshots and provider/send events to the UI for review and filtering.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k recipients/day | Single-container monolith with SQLite is appropriate |
| 1k-100k recipients/day | Move to Postgres, strengthen outbox/retry flows, consider separating heavy send execution |
| 100k+ recipients/day | Split scheduler/execution roles and use durable queues/workers |

### Scaling Priorities

1. **First bottleneck:** scheduler and send throughput in a single process — fix with better persistence, controlled concurrency, and eventually externalized execution.
2. **Second bottleneck:** database write amplification from logs/events — fix by moving from SQLite to Postgres and tightening event retention policy.

## Anti-Patterns

### Anti-Pattern 1: “Send directly from the button click”

**What people do:** Trigger generation and sending inline from the UI request without a persisted run lifecycle.
**Why it's wrong:** You lose auditability, retries, and clean failure recovery.
**Do this instead:** Create a run record first, then execute generation/sending through a service pipeline.

### Anti-Pattern 2: “MCP all the way down”

**What people do:** Make the application’s core send architecture depend directly on an MCP tool protocol.
**Why it's wrong:** Tool protocols are a poor substitute for stable application service boundaries.
**Do this instead:** Keep a delivery service boundary and let MCP be an edge integration if the agent layer truly needs it.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LiteLLM | Backend provider service | Centralize model/provider routing here |
| Resend | Delivery service boundary | Send, list status, reconcile events/webhooks, and keep local logs |
| Resend MCP | Optional edge adapter for agent-native tasks | Do not make it the only transport contract |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| UI ↔ API | HTTP + JSON | Keep UI free of provider/send secrets |
| API ↔ domain services | Direct calls | Routes should be thin |
| Domain services ↔ integrations | Narrow adapter interfaces | Prevent vendor-specific sprawl |
| Scheduler ↔ run orchestrator | Function/service call with persisted run IDs | Same execution path for manual and scheduled runs |

## Sources

- FastAPI docs: https://fastapi.tiangolo.com/tutorial/background-tasks/
- APScheduler docs: https://apscheduler.readthedocs.io/en/stable/userguide.html
- LiteLLM docs: https://docs.litellm.ai/
- Resend MCP docs: https://resend.com/mcp
- Resend API reference: https://resend.com/docs/api-reference/introduction
- React Email docs: https://react.email/docs/utilities/render
- Django auth docs: https://docs.djangoproject.com/en/5.0/topics/auth/default/

---
*Architecture research for: self-hosted AI-assisted newsletter operations app*
*Researched: 2026-04-09*
