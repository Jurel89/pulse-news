<!-- GSD:project-start source:PROJECT.md -->
## Project

**Pulse News**

Pulse News is a self-hosted newsletter operations app for a single operator. It provides a responsive web UI to create, schedule, run, review, and delete newsletters, with AI-assisted content generation, reusable email templates, audience targeting, execution logs, and delivery history.

The product is designed to run as one Dockerized service with an integrated backend, scheduler, database, and frontend bundle. It should let the operator manage multiple newsletters with distinct prompts, providers, and aesthetics while keeping sending and observability centralized.

**Core Value:** One operator can reliably create and send multiple AI-assisted newsletters from a single, self-hosted control panel without juggling separate tools for content generation, scheduling, sending, and auditability.

### Constraints

- **Deployment**: One Docker container — backend, scheduler, persistence, and frontend delivery must coexist in a single deployable unit.
- **Auth**: Proper single-user authentication — the app must protect the admin UI without introducing unnecessary multi-user complexity.
- **Responsiveness**: Mobile and desktop support — the UI cannot be desktop-only.
- **Observability**: Logging and dashboards are required — operators need traceability for runs, content, recipients, and delivery outcomes.
- **Provider strategy**: Broad LLM provider support — the system should not hardcode a single AI vendor.
- **Email delivery**: Resend integration is mandatory — sending must be built around Resend capabilities and constraints.
- **Dependencies**: No new dependencies without justification — stack choices should favor leverage and operational simplicity.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

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
# Backend
# Frontend
# Dev
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
- Use FastAPI + LiteLLM + React
- Because provider abstraction, prompt orchestration, and async integrations are the harder problem than raw CRUD
- Use Django with a React or HTMX frontend slice only where interactivity demands it
- Because Django includes auth and admin capabilities out of the box
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
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
