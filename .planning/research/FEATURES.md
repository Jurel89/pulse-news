# Feature Research

**Domain:** Self-hosted AI-assisted newsletter operations app
**Researched:** 2026-04-09
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Secure operator login | An email-sending admin tool cannot be publicly exposed | MEDIUM | Single-user scope lowers complexity, but session hardening still matters |
| Newsletter CRUD | Core object of the product | LOW | Title, slug, prompt, template, provider/model, recipients, schedule |
| Schedule and manual run controls | Newsletter tools are expected to support both recurring and on-demand sends | MEDIUM | Needs persistent schedule state and “run now” behavior |
| Draft preview and test send | Operators need confidence before delivery | MEDIUM | Preview HTML + plain text, and support a test recipient flow |
| Delivery history and run status | Operators need to know what was sent and whether it worked | MEDIUM | Must store content snapshot, recipients, provider/model, send result, timestamps |
| Recipient list management | Sending requires target lists | MEDIUM | v1 can keep this simple: imported/manual recipient sets per newsletter |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Newsletter-specific AI prompt + provider policy | Lets each newsletter behave like a distinct editorial agent | MEDIUM | Strong fit with the user’s stated intent |
| Template themes with reusable aesthetic systems | Keeps newsletters visually distinct without building raw HTML every time | MEDIUM | Best implemented as structured React Email templates plus theme variables |
| Multi-provider model routing/fallbacks | Avoids lock-in and keeps generation resilient | HIGH | Best centralized behind a provider service, not spread through feature code |
| Immutable content/run snapshots | Makes audit, debugging, and “what exactly went out?” easy | MEDIUM | Strong operational differentiator for a content-ops product |
| Per-run observability dashboard | Makes the app feel like an operations console rather than a form wrapper | MEDIUM | Includes generation logs, send logs, durations, and error detail |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Public newsletter website/CMS | Feels adjacent to newsletters | Pulls the roadmap into web publishing instead of operator workflow | Keep v1 operator-only and export public pages later if needed |
| Drag-and-drop email builder | Sounds user-friendly | High complexity, weak fit for an AI-assisted templated product, hard to validate in one-container v1 | Use curated template families with tokenized theme controls |
| Multi-user roles/teams | Common SaaS reflex | Adds permissions, invitation, audit, and UX complexity not requested by the user | Keep single-user auth for v1 |
| Fully autonomous sending with no approval gate | Sounds “agentic” | High risk of bad sends, duplicate sends, or brand drift | Require explicit approval/test-send patterns before recurring schedules go live |

## Feature Dependencies

```text
[Manual run]
    └──requires──> [Newsletter configuration]
                         └──requires──> [Prompt + template + recipients]

[Scheduled run]
    └──requires──> [Persistent scheduler]
                         └──requires──> [Stored newsletter configuration]

[Delivery dashboard]
    └──requires──> [Run records]
                         └──requires──> [Generation + send pipeline]

[Multi-provider routing] ──enhances──> [AI draft generation]

[Public site/CMS] ──conflicts──> [Focused operator-only v1]
```

### Dependency Notes

- **Manual run requires newsletter configuration:** the operator cannot safely trigger a run without a complete prompt, template, recipient set, and provider/model policy.
- **Scheduled run requires persistent scheduler:** schedule definitions must survive restarts and container redeploys.
- **Delivery dashboard requires run records:** dashboard credibility depends on immutable snapshots, not just live API calls to Resend.
- **Multi-provider routing enhances AI draft generation:** it is not required for a single-provider prototype, but it is a first-class requirement in this product vision.
- **Public site/CMS conflicts with focused v1:** it expands the scope into a different product class.

## MVP Definition

### Launch With (v1)

- [ ] Secure single-user authentication — required to protect the admin UI
- [ ] Newsletter CRUD with prompt, template, provider/model, recipients, and schedule configuration — required to manage the core object
- [ ] Manual run, scheduled run, and pause controls — required to make the tool operational
- [ ] Draft preview, test send, and send approval flow — required to reduce bad sends
- [ ] Resend-backed outbound delivery with logged statuses — required to satisfy the sending requirement
- [ ] Dashboard for runs, recipients, content snapshots, provider/model, and errors — required for auditability

### Add After Validation (v1.x)

- [ ] Provider fallback chains and cost-aware routing — add once the basic provider abstraction proves useful
- [ ] Better recipient segmentation and CSV import ergonomics — add once real operator workflows reveal pain points
- [ ] Template library management with theme presets — add once at least a few template families exist
- [ ] Retry and replay controls for failed runs — add once failure modes are observed in real use

### Future Consideration (v2+)

- [ ] Public subscribe/unsubscribe pages — defer until operator workflow is validated
- [ ] Team collaboration and roles — defer because it is outside the current product boundary
- [ ] Engagement analytics beyond delivery outcomes — defer until sending is stable
- [ ] Reply/inbound workflow automation — defer until outbound operations are reliable

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Single-user auth | HIGH | MEDIUM | P1 |
| Newsletter CRUD | HIGH | LOW | P1 |
| Scheduling/manual runs | HIGH | MEDIUM | P1 |
| Resend delivery integration | HIGH | MEDIUM | P1 |
| Run history dashboard | HIGH | MEDIUM | P1 |
| Prompt + provider policy per newsletter | HIGH | MEDIUM | P1 |
| Template family system | MEDIUM | MEDIUM | P2 |
| Provider fallbacks/cost routing | MEDIUM | HIGH | P2 |
| Public site/CMS | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Typical Newsletter Tools | AI Coding Tool Pattern | Our Approach |
|---------|--------------------------|------------------------|--------------|
| Provider breadth | Often single-vendor or email-only | OpenCode-style tools expose many providers behind configuration | Use a centralized provider service with broad model coverage |
| Send history | Usually delivery-focused | AI tools track session/run artifacts | Keep both send status and generation snapshot history |
| Templates | Often HTML/CMS-heavy | AI tools prefer structured config | Use React Email template families plus theme variables |
| Scheduling | Usually standard cron-like sends | AI tools emphasize manual runs | Support both recurring schedules and operator-triggered runs cleanly |

## Sources

- Resend MCP overview: https://resend.com/mcp
- Resend API reference: https://resend.com/docs/api-reference/introduction
- React Email docs: https://react.email/docs/utilities/render
- OpenCode README: https://github.com/opencode-ai/opencode

---
*Feature research for: self-hosted AI-assisted newsletter operations app*
*Researched: 2026-04-09*
