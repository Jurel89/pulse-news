# Pitfalls Research

**Domain:** Self-hosted AI-assisted newsletter operations app
**Researched:** 2026-04-09
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Duplicate sends from non-idempotent runs

**What goes wrong:**
The same newsletter run is sent twice because a manual click, scheduler restart, or retry path replays the same work without a durable run identity.

**Why it happens:**
Teams wire sending directly to UI actions or naive scheduler jobs before designing a run lifecycle.

**How to avoid:**
Create a run record first, give it a stable idempotency key, and ensure the send pipeline checks run state before dispatching.

**Warning signs:**
No immutable run IDs, no unique send attempt keys, or “run now” and scheduled execution use different code paths.

**Phase to address:**
Phase 1 or 2, before scheduled sending ships.

---

### Pitfall 2: No immutable snapshot of generated content

**What goes wrong:**
Operators can see that “something was sent” but cannot inspect the exact generated subject/body/template/provider settings that produced it.

**Why it happens:**
Developers assume the current newsletter config is enough and skip per-run snapshot storage.

**How to avoid:**
Persist immutable run snapshots including prompt, provider/model, rendered HTML/plain text, recipients, and send metadata.

**Warning signs:**
Dashboard reads only “live current newsletter settings” or cannot answer “what exactly went out last Tuesday?”

**Phase to address:**
Phase 2, alongside the first send pipeline.

---

### Pitfall 3: Provider logic leaks through the entire app

**What goes wrong:**
OpenAI-, Anthropic-, or Gemini-specific assumptions end up in routes, templates, and UI forms, making provider expansion brittle.

**Why it happens:**
The team starts with one provider and treats future expansion as “later.”

**How to avoid:**
Define one internal generation interface, one provider policy schema, and one output contract from day one.

**Warning signs:**
Feature code branches on provider names or model-specific request shapes outside the integration layer.

**Phase to address:**
Phase 1, when the backend domain and service boundaries are established.

---

### Pitfall 4: Resend MCP becomes the app architecture

**What goes wrong:**
Application delivery depends on a tool-protocol workflow instead of a stable service boundary, which makes retries, logging, and deterministic testing harder.

**Why it happens:**
MCP is attractive for agent-native workflows, so teams over-apply it to the production app core.

**How to avoid:**
Keep a delivery service boundary that owns send attempts, status reconciliation, and logs; treat MCP as an optional edge integration, not the core contract.

**Warning signs:**
The backend cannot send or reconcile mail without invoking a tool runtime, or transport logic is hidden inside prompt/tool chains.

**Phase to address:**
Phase 2, when outbound delivery is designed.

---

### Pitfall 5: Scheduler state breaks across restarts

**What goes wrong:**
Scheduled newsletters disappear, duplicate, or drift after the container restarts.

**Why it happens:**
The scheduler is kept in memory only, or jobs are re-registered on startup without stable IDs and replacement semantics.

**How to avoid:**
Use a persistent job store, explicit scheduler job IDs, and startup reconciliation that replaces existing jobs rather than duplicating them.

**Warning signs:**
Schedules only exist in memory, or every restart adds more jobs.

**Phase to address:**
Phase 2, before recurring schedules are exposed to users.

---

### Pitfall 6: “Single-user auth” implemented as weak basic auth

**What goes wrong:**
The app is technically password-protected but lacks secure session handling, password storage, logout semantics, or account bootstrap hygiene.

**Why it happens:**
Single-user scope gets mistaken for low security requirements.

**How to avoid:**
Use proper password hashing, secure session cookies, lock bootstrap flows after first setup, and build explicit logout/session invalidation behavior.

**Warning signs:**
Plain env-var passwords, HTTP basic auth for the whole app, or no concept of session expiration/logout.

**Phase to address:**
Phase 1, with the first protected UI.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| SQLite with no migration discipline | Fastest possible setup | Painful schema evolution and recovery | Only if Alembic/migrations are added immediately after initial schema creation |
| Provider-specific prompt fields in the newsletter table | Faster first prototype | Hard provider expansion and messy UI | Rarely acceptable |
| Using current newsletter config to reconstruct history | Less storage | Broken auditability and impossible debugging | Never |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LiteLLM | Treating it as “magic” with no local provider policy layer | Wrap LiteLLM in an internal generation service with explicit inputs and normalized outputs |
| Resend | Logging only provider responses, not local run intent and recipient set | Store local run records before sending and reconcile external status afterward |
| Resend MCP | Building app-critical flows around tool invocation semantics | Use MCP only where agent-native tooling is genuinely required |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Long generation/sending inside request cycle | UI hangs, browser timeouts, duplicate clicks | Queue work into a persisted run lifecycle and return immediate accepted state | Immediately under moderate latency |
| Over-fetching run history with full rendered bodies | Slow dashboard pages | Paginate and summarize list views; fetch full snapshot on detail view | Hundreds to thousands of runs |
| SQLite under growing concurrent writes | Locking or slow writes during send bursts | Keep concurrency bounded and move to Postgres if run volume meaningfully grows | Usually first visible at higher send frequency or multiple concurrent runs |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Weak single-user auth | Unauthorized access to subscriber data and outbound email capability | Proper password hashing, secure sessions, bootstrap locking, CSRF/session hygiene |
| Storing provider or Resend secrets in frontend-visible config | Secret leakage | Keep all secrets server-side and expose only safe config to the UI |
| Logging full secrets or raw auth headers in run logs | Credential compromise | Redact tokens and structure logs intentionally |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No preview/test-send step | Fear of sending broken newsletters | Make preview and test send explicit parts of the workflow |
| Conflating newsletter config with per-run results | Operators cannot tell config drift from actual sent output | Separate “current definition” from “historical runs” in the UI |
| Desktop-only operational UI | Poor mobile administration despite explicit requirement | Design mobile and desktop layouts from the first dashboard pass |

## "Looks Done But Isn't" Checklist

- [ ] **Authentication:** Often missing session invalidation and secure bootstrap — verify logout and first-user setup flows
- [ ] **Scheduling:** Often missing restart persistence — verify schedules survive container restart without duplication
- [ ] **Sending:** Often missing idempotency — verify one run cannot dispatch twice accidentally
- [ ] **Dashboard:** Often missing immutable content snapshots — verify historical detail is not reconstructed from current config
- [ ] **Provider support:** Often missing normalized error handling — verify provider failures surface consistently in the UI

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Duplicate sends | HIGH | Pause schedules, identify duplicate run keys, notify recipients if needed, and patch idempotency before resuming |
| Missing content snapshots | HIGH | Backfill only partial history if provider logs exist; otherwise accept data loss and fix schema immediately |
| Scheduler duplication after restart | MEDIUM | Clear/reconcile persisted jobs, enforce explicit IDs with replace behavior, and replay known-good schedules |
| Provider abstraction leakage | MEDIUM | Introduce integration boundary, refactor provider-specific branches inward, and normalize errors/outputs |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Duplicate sends | Phase 2 | Manual run and scheduled run share one idempotent execution path |
| Missing snapshots | Phase 2 | Every run detail view shows stored subject/body/template/provider metadata |
| Provider leakage | Phase 1 | Non-integration modules do not branch on provider names |
| Resend MCP overreach | Phase 2 | Delivery service can operate deterministically without a tool-runtime dependency |
| Scheduler restart drift | Phase 2 | Restart test preserves schedules without duplication |
| Weak single-user auth | Phase 1 | Protected routes require secure sessions and bootstrap is one-time |

## Sources

- FastAPI docs: https://fastapi.tiangolo.com/tutorial/background-tasks/
- APScheduler docs: https://apscheduler.readthedocs.io/en/stable/userguide.html
- LiteLLM docs: https://docs.litellm.ai/
- Resend MCP docs: https://resend.com/mcp
- Resend API reference: https://resend.com/docs/api-reference/introduction
- Django auth docs: https://docs.djangoproject.com/en/5.0/topics/auth/default/

---
*Pitfalls research for: self-hosted AI-assisted newsletter operations app*
*Researched: 2026-04-09*
