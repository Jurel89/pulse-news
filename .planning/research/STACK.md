# Stack Research

**Domain:** Self-hosted AI-assisted newsletter operations app
**Researched:** 2026-04-09
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13 | Backend runtime | Best fit for AI-provider abstraction, prompt orchestration, and scheduler-heavy application logic in a single service. |
| FastAPI | 0.135.3 | HTTP API, auth/session endpoints, admin backend | FastAPI natively supports background tasks and async APIs, which fits operator-triggered runs and integrations while keeping the backend lightweight. |
| React | 19.2.5 | Responsive operator UI | The UI needs dynamic scheduling, previews, run history, and mobile/desktop responsiveness; React is justified for that level of interactivity. |
| Vite | 8.0.8 | Frontend build tool | Keeps the React admin app lightweight and easy to bundle into the single backend container. |
| SQLite | 3.x | Default app database | The product is explicitly single-user and single-container; SQLite minimizes operational overhead for v1 while still supporting audit/history storage. |
| SQLAlchemy | 2.0.49 | ORM and persistence layer | Mature Python persistence foundation for newsletters, runs, logs, recipients, and scheduler metadata. |
| APScheduler | 3.11.2 | In-process scheduling | APScheduler supports background schedulers and persistent SQLAlchemy-backed job stores, which fits a one-container scheduler model. |
| LiteLLM | 1.83.4 | Multi-provider LLM abstraction | LiteLLM exposes an OpenAI-compatible interface, supports 100+ providers, and provides routing/fallbacks without building custom adapters for every vendor. |
| React Email render | 2.0.6 | HTML + plain-text email template rendering | Official React Email utilities render React components to HTML and plain text, which fits reusable newsletter template themes. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pydantic Settings | bundled with FastAPI ecosystem | Typed configuration management | Use for app config, provider secrets, Resend credentials, and feature flags. |
| Alembic | current stable | Database migrations | Use immediately once the first schema exists; audit tables should not rely on ad hoc migrations. |
| Passlib or pwdlib | current stable | Password hashing | Use for the single local operator account if staying on FastAPI rather than Django auth. |
| itsdangerous or signed session middleware | current stable | Secure session cookies / bootstrap tokens | Use for one-user login flows, bootstrap account creation, and password reset/session invalidation. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Backend testing | Cover scheduler behavior, provider adapters, send orchestration, and idempotency. |
| Playwright | UI and E2E verification | Required for mobile/desktop admin flows, auth, and send-history visibility. |
| Ruff | Python lint/format | Keeps backend/tooling friction low in a greenfield repo. |
| TypeScript | Frontend safety | Use with React to keep form- and dashboard-heavy UI reliable. |

## Installation

```bash
# Backend
pip install fastapi==0.135.3 sqlalchemy==2.0.49 apscheduler==3.11.2 litellm==1.83.4 sqlmodel==0.0.38

# Frontend
npm install react@19.2.5 vite@8.0.8 @react-email/render@2.0.6

# Dev
pip install pytest ruff alembic
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| FastAPI + React | Django + server-rendered admin/HTMX | Use Django if the product becomes CRUD-heavy and the custom dashboard/workflow UI turns out to be much thinner than expected. Django’s built-in auth/admin are strong, but a scheduling + AI-ops UI usually outgrows “mostly admin pages.” |
| LiteLLM-backed provider service | Hand-rolled direct adapters to each provider | Use direct adapters only if LiteLLM becomes a concrete blocker for a required provider/model behavior or cost-routing policy. |
| FastAPI + React | Full-stack Next.js | Use Next.js if the team chooses TypeScript end-to-end and accepts rebuilding provider orchestration away from Python-centric tooling. For this product, that adds more churn than leverage. |
| SQLite-first single container | Postgres from day one | Use Postgres earlier only if recipient volume, concurrent runs, or deployment policy make SQLite durability/concurrency unacceptable. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Building provider support as one adapter per vendor inside feature code | The abstraction leaks everywhere and makes model/provider expansion expensive | Centralize provider/model access behind LiteLLM and an internal generation service |
| Treating Resend MCP as the app’s primary transport architecture | MCP is a tool protocol, not the cleanest core boundary for a production app service | Keep a local outbound email service boundary and implement it first with official Resend API semantics; add MCP compatibility at the edge if needed |
| Splitting scheduler, API, worker, and frontend into multiple containers for v1 | Violates the deployment constraint and adds coordination complexity too early | Keep one process tree/container with explicit service boundaries inside the codebase |
| A public marketing site or subscriber portal in the same v1 scope | Pulls the roadmap away from the operator workflow the user actually asked for | Focus on operator-only newsletter management first |

## Stack Patterns by Variant

**If the priority stays “best AI/provider leverage”:**
- Use FastAPI + LiteLLM + React
- Because provider abstraction, prompt orchestration, and async integrations are the harder problem than raw CRUD

**If the priority shifts to “lowest custom-auth/admin work”:**
- Use Django with a React or HTMX frontend slice only where interactivity demands it
- Because Django includes auth and admin capabilities out of the box

**If the product later becomes team-facing SaaS rather than self-hosted single-user:**
- Move from SQLite to Postgres and from in-process scheduling to a dedicated execution/outbox strategy
- Because audit, concurrency, and scheduler coordination get materially harder

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| FastAPI 0.135.3 | Pydantic v2 ecosystem | Current FastAPI docs and package line target the modern Pydantic stack |
| APScheduler 3.11.2 | SQLAlchemy-backed persistent job stores | Matches the documented SQLAlchemy job store pattern for persistent schedules |
| React 19.2.5 | Vite 8.0.8 | Current mainstream frontend baseline for a greenfield admin UI |
| LiteLLM 1.83.4 | OpenAI-compatible provider abstraction | Fits a provider-router boundary instead of vendor-specific SDK sprawl |

## Sources

- FastAPI docs: https://fastapi.tiangolo.com/tutorial/background-tasks/ — background task model and single-app async backend patterns
- APScheduler docs: https://apscheduler.readthedocs.io/en/stable/userguide.html — persistent job stores, background schedulers, SQLAlchemy job store guidance
- LiteLLM docs: https://docs.litellm.ai/ — OpenAI-compatible multi-provider access, routing, fallbacks, and 100+ provider support
- LiteLLM site: https://www.litellm.ai/ — gateway and provider breadth overview
- React docs: https://react.dev/learn — current React baseline for interactive UIs
- Next.js docs: https://nextjs.org/docs/app/getting-started/installation — current full-stack TypeScript alternative baseline
- Django overview: https://www.djangoproject.com/start/overview/ — built-in auth/admin/security tradeoffs
- Django auth docs: https://docs.djangoproject.com/en/5.0/topics/auth/default/ — default auth system capabilities
- React Email docs: https://react.email/docs/utilities/render — React-based email template rendering
- OpenCode README: https://github.com/opencode-ai/opencode — confirms multi-provider support is built directly rather than clearly centered on LiteLLM

---
*Stack research for: self-hosted AI-assisted newsletter operations app*
*Researched: 2026-04-09*
