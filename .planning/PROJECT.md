# Pulse News

## What This Is

Pulse News is a self-hosted newsletter operations app for a single operator. It provides a responsive web UI to create, schedule, run, review, and delete newsletters, with AI-assisted content generation, reusable email templates, audience targeting, execution logs, and delivery history.

The product is designed to run as one Dockerized service with an integrated backend, scheduler, database, and frontend bundle. It should let the operator manage multiple newsletters with distinct prompts, providers, and aesthetics while keeping sending and observability centralized.

## Core Value

One operator can reliably create and send multiple AI-assisted newsletters from a single, self-hosted control panel without juggling separate tools for content generation, scheduling, sending, and auditability.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Operator can authenticate into a single-user admin UI securely from desktop and mobile devices.
- [ ] Operator can create, edit, schedule, run manually, pause, and delete newsletters.
- [ ] Operator can define newsletter-specific prompts, recipients, sending settings, and aesthetic templates.
- [ ] Operator can generate newsletter drafts through multiple LLM providers behind a common abstraction layer.
- [ ] Operator can send newsletters through Resend and review a delivery and execution dashboard with logs, content snapshots, recipients, and statuses.

### Out of Scope

- Public subscriber-facing landing pages or subscription forms — initial scope is an operator tool, not a public marketing site.
- Multi-user collaboration or role-based access control — user requested proper single-user authentication only.
- Multi-container orchestration with separate workers, queues, or databases — deployment must fit in one Docker container.

## Context

This repository starts greenfield with no existing application code. The user wants a single-container product with a Python-leaning backend and React-capable frontend, but explicitly asked for critical evaluation of the stack before locking it in.

The domain combines newsletter operations, AI content generation, scheduling, and auditability. Each newsletter needs its own intent prompt, visual template, provider/model selection, recipients, and scheduling rules. The UI must expose operational history: what was sent, to whom, when, with which content, and with what provider/send result.

The user also wants provider coverage inspired by OpenCode. Initial research indicates OpenCode directly supports multiple providers plus a self-hosted OpenAI-compatible endpoint, rather than delegating to LiteLLM by default. That means provider architecture is a real early decision, not just an implementation detail.

The sending layer must integrate with Resend. Resend currently supports sending, scheduling, templates, webhooks, inbound mail, and an MCP server that exposes those capabilities to agents. The product should treat Resend as the authoritative delivery platform while preserving local execution logs and content history.

## Constraints

- **Deployment**: One Docker container — backend, scheduler, persistence, and frontend delivery must coexist in a single deployable unit.
- **Auth**: Proper single-user authentication — the app must protect the admin UI without introducing unnecessary multi-user complexity.
- **Responsiveness**: Mobile and desktop support — the UI cannot be desktop-only.
- **Observability**: Logging and dashboards are required — operators need traceability for runs, content, recipients, and delivery outcomes.
- **Provider strategy**: Broad LLM provider support — the system should not hardcode a single AI vendor.
- **Email delivery**: Resend integration is mandatory — sending must be built around Resend capabilities and constraints.
- **Dependencies**: No new dependencies without justification — stack choices should favor leverage and operational simplicity.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Treat this as a greenfield operator tool, not a public SaaS product | Matches the single-user, self-hosted requirement and keeps v1 focused | — Pending |
| Prefer a unified single-container architecture with in-process scheduling | Avoids queue/worker/container sprawl and fits deployment constraints | — Pending |
| Research provider abstraction before locking the backend stack | Provider breadth and model routing shape backend design materially | — Pending |
| Keep React-class UI capability in scope, but validate whether FastAPI+React or Django-first is the better delivery path | User asked for criticism of the stack, not blind acceptance | — Pending |
| Use Resend as the sending system of record while storing local execution history | Satisfies mandatory integration and dashboard/audit requirements | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-09 after initialization*
