# Pulse News — product audit, UX review, and detailed implementation plan

**Date:** 2026-04-11  
**Repository snapshot reviewed:** `pulse-news-main`  
**Document status:** Proposed implementation brief  
**Audience:** Product, design, architecture, backend, frontend, and operations

---

## 1. Purpose

This document consolidates the current product audit for **Pulse News** into a single implementation brief. It is intended to do four things:

1. Describe the current product problems from a real operator and editor perspective.
2. Record the concrete bugs and architectural inconsistencies confirmed in the current codebase.
3. Define the target product model and information architecture.
4. Provide a phased, fully detailed implementation plan that is modular, secure, maintainable, and future-proof.

This is not a visual design spec. It is a product architecture and delivery plan for rebuilding the platform into a coherent self-hosted newsletter system.

---

## 2. Basis of this review

This document is grounded in the current repository structure and code paths, especially:

- `frontend/src/App.tsx`
- `frontend/src/features/providers/*`
- `frontend/src/features/api-keys/*`
- `frontend/src/features/newsletters/*`
- `frontend/src/features/templates/*`
- `frontend/src/features/dashboard/RunDashboardPage.tsx`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/ai_generation.py`
- `backend/app/email_templates.py`
- `backend/app/email_delivery.py`
- `backend/app/api/providers.py`
- `backend/app/api/api_keys.py`
- `backend/app/api/newsletters.py`
- `backend/app/api/email_templates.py`
- `backend/app/api/runs.py`
- `backend/app/api/public.py`
- `backend/app/api/webhooks.py`

Where relevant, code references are included. Line numbers are based on the current snapshot and may drift over time.

---

## 3. Executive summary

### 3.1 The main problem

The core problem is **not** just that the UI looks weak.

The deeper problem is that the product model is inconsistent with how users think about the system. The application is still **field-centric**, while users think in terms of **tasks and workflows**.

Users think like this:

1. Add a secret.
2. Connect an AI provider.
3. Validate the connection.
4. Discover models.
5. Enable the models they actually want.
6. Configure delivery.
7. Choose or build a template.
8. Draft a newsletter.
9. Preview and test it safely.
10. Send or schedule it.
11. Observe runs and fix failures.

Pulse News currently forces users to think like this instead:

- choose a provider type from a hardcoded list
- assign an API key from a provider-specific dropdown
- type JSON by hand
- pick from a template key list
- assume that “test” means real validation
- paste recipients into a textarea
- understand the difference between environment credentials, per-newsletter overrides, provider records, and delivery settings

That inversion is why the app feels brittle and unintuitive.

### 3.2 The current structural failure

The platform has too many competing sources of truth:

- provider type is hardcoded in backend schema validation, frontend dropdowns, and AI generation logic
- model catalogs are hardcoded in frontend and backend, while newsletters also read configured provider models
- templates exist both as built-in runtime fallbacks and database records
- newsletters store both relational references and denormalized names/keys
- secrets are mixed with provider semantics
- delivery credentials are handled partly through environment configuration and partly through newsletter-level overrides

This causes drift, hidden fallback behavior, and configuration states that are technically valid in the database but invalid in the product.

### 3.3 What must happen first

Do **not** start with cosmetic polish or with “add more providers” on top of the current architecture.

The immediate order of work should be:

1. fix correctness and security failures
2. normalize the domain model
3. separate secrets, AI providers, templates, and delivery
4. rebuild provider/model management
5. rebuild template management
6. rebuild newsletter authoring flow
7. add audience and operations surfaces
8. expand provider coverage

If this order is reversed, the team will spend time polishing a structure that is actively fighting the product.

---

## 4. Root-cause diagnosis

## 4.1 Pulse News is modeling implementation details, not operator workflows

The current app exposes internal storage choices directly in the UI:

- raw provider type strings
- raw JSON configuration fields
- template keys
- AI API key selection in the newsletter editor
- raw cron expressions
- per-newsletter Resend key overrides
- fallback rules hidden behind tests and send actions

A well-designed operator product should expose:

- connection states
- health states
- enablement states
- previews
- blockers
- guided next actions
- safe defaults
- explicit overrides only when needed

Pulse News currently inverts that: it exposes the override surface before the primary workflow is even sound.

## 4.2 The product leaks multiple sources of truth everywhere

The most harmful pattern in the codebase is duplicated state.

Examples:

- `Newsletter` stores `provider_id` **and** `provider_name` (`backend/app/models.py:107-113`)
- `Newsletter` stores `template_id` **and** `template_key` (`backend/app/models.py:114-119`)
- provider support is hardcoded in `SupportedProvider` (`backend/app/schemas.py:41-48`)
- provider support is hardcoded again in `SUPPORTED_PROVIDERS` (`backend/app/ai_generation.py:26`)
- provider model catalogs are hardcoded in the backend (`backend/app/api/providers.py:22-32`)
- provider model catalogs are hardcoded again in the frontend (`frontend/src/features/providers/provider-types.ts:26-44`)
- templates can come from database rows or built-in fallback keys (`backend/app/api/newsletters.py:472-486`, `backend/app/email_templates.py:107-125`)

This is why the current UX cannot be made reliable by styling alone.

## 4.3 The product currently teaches users through failure

The current UX depends too much on backend rejection or hidden fallback behavior:

- invalid setup states are allowed to persist
- tests do not test the real upstream integration
- send flows do not clearly surface blockers before action
- template preview does not fully match actual render behavior
- destructive actions can silently alter rendering behavior

A serious newsletter platform should guide users to a valid state before they can perform risky actions.

---

## 5. User-perspective audit

This section reframes the product from the perspective of the people actually using it.

## 5.1 First-time admin / self-hosted operator

### What the user is trying to do
“I just installed Pulse News. I want to get to a safe first send as quickly as possible.”

### Current experience
The system gives the user isolated forms instead of a guided setup path. The operator has to infer:

- what belongs to AI generation vs email delivery
- whether API keys should be stored globally or per newsletter
- what “provider” really means
- whether models are discovered or hardcoded
- where to start with templates
- how delivery credentials work
- whether a test is trustworthy

### Result
The user has to reverse-engineer the platform before they can trust it.

### Required target experience
The first-run story should be a checklist or wizard:

1. create first secret
2. connect AI provider
3. validate provider
4. discover and enable models
5. connect delivery provider
6. verify sender identity / domain
7. choose template
8. create sample newsletter
9. send safe test
10. review health status

## 5.2 AI provider administrator

### What the user is trying to do
“I want to connect an LLM provider, verify the connection, see available models, and choose which ones are enabled.”

### Current experience
The provider page mixes several unrelated concerns:

- provider type is fixed from a hardcoded list
- model selection is hardcoded from frontend constants
- configuration is a raw JSON textarea
- test connection only checks local database state
- create flow does not support pre-save testing
- no real model discovery exists for configured providers

### Result
The user cannot trust the setup page, and the architecture blocks provider expansion.

### Required target experience
Provider management should support:

- provider catalog
- “Add provider” wizard
- secret binding
- config schema-based form rendering
- pre-save validation
- real upstream connection test
- model discovery or manual model entry
- enable/disable models
- default model selection
- health state and last tested timestamp

## 5.3 Secret / credential owner

### What the user is trying to do
“I want one place where secrets are stored safely, rotated safely, and reused safely.”

### Current experience
The current API keys page is not a neutral vault. It asks for provider-specific types in the same surface where credentials are stored, and secrets are persisted in plaintext in the database (`backend/app/models.py:77-85`).

### Result
The system is not functioning like a secure secret-management surface.

### Required target experience
The page should become **Secrets**, not **API Keys**, with:

- encrypted-at-rest storage
- neutral secret types
- provider hint optional, not mandatory
- last validated
- last used
- usage references
- rotate / deactivate
- source awareness (`db`, `env`, external reference)

## 5.4 Newsletter editor / content operator

### What the user is trying to do
“I want to create a newsletter quickly, choose a template, preview it, test it, and send it.”

### Current experience
The editor is a long form with many loosely related fields:

- provider
- model
- AI key
- Resend key
- template
- audience name
- delivery topic
- timezone
- cron
- notes
- recipients

All of this appears in one large form in `frontend/src/features/newsletters/NewsletterEditorPage.tsx`.

### Result
The user has to manage setup complexity inside the content authoring flow.

### Required target experience
Newsletter authoring should be step-based:

1. basics
2. content / prompting
3. AI provider and model
4. template and preview
5. audience
6. delivery
7. schedule
8. review / preflight

## 5.5 Template author

### What the user is trying to do
“I want to start from a good base template, preview it with realistic data, version it, and use it safely.”

### Current experience
The template page is a raw HTML editor with a preview button and a small hint about available variables. It lacks:

- gallery with thumbnails
- built-in template parity
- version history
- clone / duplicate
- clear schema of supported variables
- live split-view editing
- linting
- preview-before-first-save
- rollback
- archive

### Result
Templates feel like a low-level development artifact, not a product feature.

### Required target experience
Templates should be a registry with:

- system and custom templates in one gallery
- thumbnails
- versioning
- preview data presets
- duplicate
- archive
- compatibility checks
- explicit variables and merge-field schema

## 5.6 Audience manager

### What the user is trying to do
“I want to manage subscribers, segments, suppression, imports, and preferences.”

### Current experience
Audience handling is essentially a pasted email list per newsletter. The current system has unsubscribe support and recipient status tracking, but not an actual audience product surface. The code supports `NewsletterRecipient`, unsubscribe tokens, and suppression reasons, but there is no reusable audience model and no public subscribe flow. There is only unsubscribe handling (`backend/app/api/public.py`).

### Result
Audience management is operationally primitive.

### Required target experience
Audience should become a first-class domain with:

- contacts
- lists / segments
- tags
- suppression list
- import workflow
- export workflow
- public subscribe endpoint
- opt-in strategy
- topic preferences

## 5.7 Delivery operator

### What the user is trying to do
“I need to know whether sending is configured correctly and what will happen when I send.”

### Current experience
Delivery is effectively “Resend plus environment fallback plus optional newsletter override.” It is not modeled as a delivery profile. Test send can simulate success when live delivery is not configured, while production send can fail under those same conditions (`backend/app/email_delivery.py:385-466`).

### Result
The user cannot trust send validation.

### Required target experience
Delivery should be a separate bounded context with:

- delivery profiles
- provider selection
- sender configuration
- domain verification status
- webhook health
- real send preflight
- explicit fallback policy

## 5.8 Operations / maintainer

### What the user is trying to do
“I need to know what ran, what failed, why, and what to do next.”

### Current experience
The run dashboard exists, but it is still a raw operational view:

- no health overview
- no grouped failures
- no stage timeline
- no retry / replay actions
- no preflight visibility
- no audit UI
- no scheduler state
- no provider health summary
- no delivery health summary

### Result
The operator still needs logs and code knowledge to diagnose the system.

### Required target experience
Operations should expose:

- system health dashboard
- provider health
- delivery health
- scheduler status
- webhook status
- recent failures
- run stage detail
- audit trail
- actionable remediation

---

## 6. Confirmed defects and structural issues

This section records the most important problems confirmed from the current code.

## 6.1 P0 — Provider toggle can wipe provider configuration

**Type:** Data loss / configuration integrity  
**Evidence:** `frontend/src/App.tsx:298-308`, `backend/app/api/providers.py:123-152`

### What happens
The frontend toggle action updates a provider without including `configuration`. The backend update handler then assigns:

```python
provider.configuration = payload.configuration
```

That means a simple enable/disable toggle can overwrite the provider configuration with `null`.

### Why this is severe
Configuration can contain model lists or other provider-specific options. Toggling enablement should never destroy setup state.

### User impact
A user disables or re-enables a provider and silently loses configuration.

### Required fix
- replace `PUT`-style destructive update behavior with `PATCH` semantics or preserve existing values when fields are omitted
- add regression tests to ensure toggles do not mutate unrelated fields
- disable the current toggle path until the backend is safe

### Acceptance criteria
- toggling enabled state preserves configuration exactly
- audit log records only the enablement change
- tests fail if `configuration` changes during toggle

## 6.2 P0 — Template deletion can silently change newsletter rendering

**Type:** Rendering integrity / silent fallback  
**Evidence:** `backend/app/models.py:114-119`, `backend/app/api/newsletters.py:427`, `backend/app/api/newsletters.py:734`, `backend/app/api/email_templates.py:224-225`, `backend/app/email_templates.py:107-125`

### What happens
Newsletters store both `template_id` and `template_key`, but newsletter create/update paths persist `template_key`, not `template_id`. Deleting a template only nulls `template_id`.

At render time, the system resolves by `template_key`, and if resolution fails it falls back to a built-in template, usually `signal`.

### Why this is severe
Deleting a custom template can cause an existing newsletter to render with a different layout without any explicit user acknowledgement.

### User impact
A newsletter that used a deleted custom template may send with a fallback built-in layout.

### Required fix
- pick one canonical reference: `template_version_id` or at minimum `template_id`
- remove silent template fallback for deleted or missing custom templates
- block deletion of in-use templates, or require explicit migration to another template
- expose a migration UI when retiring templates

### Acceptance criteria
- deleting a template in use is blocked or forces reassignment
- preview and send fail clearly if the assigned template is invalid
- no newsletter silently switches layout

## 6.3 P0 — Newsletters can persist logically invalid provider/key combinations

**Type:** Referential integrity / domain validation  
**Evidence:** `backend/app/api/newsletters.py:409-465`, `backend/app/schemas.py:156-223`, `backend/app/ai_generation.py:73-117`

### What happens
The API validates field formats, but not cross-entity compatibility. A newsletter can reference:

- a provider instance of one type
- an API key of another type
- a model that does not belong to the selected provider instance

### Why this is severe
The database accepts states that are not valid in the product.

### User impact
The user only discovers the problem later, in generation or delivery, instead of at configuration time.

### Required fix
Introduce server-side validation service for newsletter composition:

- provider instance must exist and be enabled
- selected model must belong to the provider instance
- AI secret must be compatible with the provider adapter
- delivery profile must exist and be healthy enough for the selected action
- template must exist and resolve unambiguously

### Acceptance criteria
- invalid cross-entity combinations are rejected with `422`
- error messages explain the exact invalid reference
- UI preflight blocks invalid saves before submission where possible

## 6.4 P0 — Secrets are stored in plaintext

**Type:** Security  
**Evidence:** `backend/app/models.py:77-85`

### What happens
`ApiKey.key_value` is stored as plaintext.

### Why this is severe
This is unacceptable for a platform that is supposed to manage third-party credentials, especially in self-hosted deployments where admins still expect sane defaults.

### User impact
Database compromise exposes live provider and delivery credentials.

### Required fix
- replace `api_keys` concept with encrypted `secrets`
- encrypt at rest using AES-GCM or equivalent, with a master key sourced from environment or external KMS
- store key version metadata to support rotation
- expose the full secret only on creation
- store display-safe metadata separately from ciphertext

### Acceptance criteria
- no plaintext secret values are persisted
- secret rotation is supported
- audit events record validation and rotation, not full values
- last-used and last-validated timestamps are tracked

## 6.5 P1 — Provider support is hardcoded in multiple places

**Type:** Extensibility blocker  
**Evidence:** `backend/app/schemas.py:41-48`, `backend/app/ai_generation.py:26`, `backend/app/api/providers.py:22-32`, `frontend/src/features/providers/provider-types.ts:26-44`, `frontend/src/features/api-keys/api-key-types.ts:21-28`

### What happens
Provider support is baked into:

- backend schema enums
- generation logic
- provider model catalogs
- frontend provider dropdowns
- API key provider dropdowns

### Why this matters
Adding providers like **Z.AI** and **Kimi** should not require touching multiple files across backend validation, frontend options, and generation logic.

### User impact
Provider expansion is slow, brittle, and guaranteed to drift.

### Required fix
Move to an adapter registry and provider preset registry. Validation should be driven by adapter metadata, not hardcoded string enums spread across the stack.

### Acceptance criteria
- adding a provider preset requires registering one adapter/preset definition
- frontend provider forms are generated from backend-delivered metadata
- provider support does not require parallel manual edits in multiple layers

## 6.6 P1 — Model discovery has three inconsistent sources of truth

**Type:** Data consistency / UX trust failure  
**Evidence:** `frontend/src/features/providers/provider-types.ts:34-44`, `backend/app/api/providers.py:22-32`, `backend/app/api/newsletters.py:502-523`

### What happens
Models come from:

1. a hardcoded frontend catalog
2. a hardcoded backend catalog
3. provider configuration JSON parsed at newsletter form time

### Why this matters
The product can show one model set on the provider page, another in the editor, and a third in runtime.

### User impact
Users do not know which models are actually configured or usable.

### Required fix
Persist a provider-model catalog per provider instance. The newsletter editor should only read enabled models from that catalog.

### Acceptance criteria
- one durable provider-model catalog exists per provider instance
- all pages read from the same model source
- discovery results are visible, editable, and timestamped

## 6.7 P1 — Provider test is not a real upstream connection test

**Type:** False-positive validation  
**Evidence:** `backend/app/api/providers.py:193-231`

### What happens
“Test connection” only checks:

- whether the provider is enabled
- whether any active API key exists for that provider type

It does not validate:

- JSON config correctness
- upstream authentication
- model availability
- base URL correctness
- provider capability compatibility

### User impact
The user gets a success message that does not prove the provider works.

### Required fix
Implement real adapter-level validation:

- validate config schema
- retrieve or call a lightweight upstream endpoint
- confirm auth works
- optionally verify default model availability
- record latency, health, and validation result

### Acceptance criteria
- invalid endpoint or invalid secret fails the test
- test results include timestamp and reason
- test flow can run before saving the provider record

## 6.8 P1 — API key test is not a real secret validation

**Type:** False-positive validation  
**Evidence:** `backend/app/api/api_keys.py:184-205`

### What happens
The current test only checks whether the key is active and whether an enabled provider of the same type exists.

### User impact
The user can be told a key is valid when the upstream provider would reject it.

### Required fix
Secret validation must be adapter-aware and must optionally test upstream auth.

### Acceptance criteria
- invalid secrets fail validation
- a secret can be validated independently of provider existence
- validation details are stored and surfaced

## 6.9 P1 — Test send behavior diverges from real send behavior

**Type:** Trust failure / unsafe workflow  
**Evidence:** `backend/app/email_delivery.py:385-466`

### What happens
Test send returns a simulated success when Resend is not configured. Real send in production raises an error when delivery credentials are missing.

### User impact
The user thinks sending is configured because test send “worked,” but a live send later fails.

### Required fix
Align test send and real send prerequisites. A test should either:

- validate the same delivery prerequisites as live send, or
- clearly state that it was a local preview only and should not be interpreted as delivery readiness

### Acceptance criteria
- production-mode test send cannot report success without live delivery configuration
- UI visibly distinguishes preview-only from real provider send
- send preflight reflects exact live requirements

## 6.10 P1 — Run reconciliation may use the wrong delivery credential

**Type:** Operational correctness  
**Evidence:** `backend/app/api/runs.py:120-125`, `backend/app/email_delivery.py:525+`

### What happens
Run reconciliation calls `retrieve_email_status()` without passing the newsletter or delivery configuration that was used during send. If a run used newsletter-specific Resend credentials, reconciliation may use the wrong credential path later.

### User impact
Delivery status reconciliation can become inaccurate.

### Required fix
Run snapshots must store the exact delivery profile or credential reference used for the send, and reconciliation must use that snapshot.

### Acceptance criteria
- reconciliation uses the same delivery context as the original send
- run snapshot contains immutable delivery metadata
- status lookups remain correct after provider or secret changes

## 6.11 P1 — Newsletter preview and runtime template behavior do not fully match

**Type:** Preview correctness  
**Evidence:** `backend/app/api/email_templates.py:24-32`, `backend/app/api/email_templates.py:96-106`, `backend/app/email_templates.py:79-87`

### What happens
Template preview and runtime rendering use different substitution logic:

- preview uses a regex-based placeholder replacer with default preview variables
- runtime custom rendering uses a fixed set of `str.replace()` calls

One concrete mismatch: `{{newsletter_name}}` resolves to `"Pulse News"` in preview defaults, but at runtime it is replaced with the **subject**, not the newsletter name (`backend/app/email_templates.py:86`).

### User impact
Preview can differ from the actual rendered email.

### Required fix
Use one shared rendering engine for preview and runtime, with one canonical variable schema.

### Acceptance criteria
- preview and runtime render use the same code path
- merge variables have one documented meaning
- templates using `{{newsletter_name}}` resolve consistently

## 6.12 P1 — Built-in templates are not consistently represented in the template system

**Type:** Product inconsistency  
**Evidence:** `backend/app/api/email_templates.py:109-117`, `backend/app/api/newsletters.py:472-486`, `backend/app/email_templates.py:107-125`

### What happens
The template listing endpoint returns only database templates. The newsletter form options append built-in `signal` and `ledger` templates even if they do not exist in the database.

### User impact
A template can be selectable in the newsletter editor while being absent from the templates page.

### Required fix
Seed system templates into the same canonical template registry and stop appending ad hoc built-ins elsewhere.

### Acceptance criteria
- all selectable templates appear in the templates page
- system templates are first-class records
- template selection comes from one canonical source

## 6.13 P1 — Provider and template identity are duplicated on the newsletter model

**Type:** Source-of-truth drift  
**Evidence:** `backend/app/models.py:107-119`

### What happens
`Newsletter` stores:

- `provider_id` and `provider_name`
- `template_id` and `template_key`

### Why this matters
A record can partially update and drift out of sync. Deleting a provider or template can leave stale denormalized values that continue to affect behavior.

### Required fix
Use canonical relational references for the editable newsletter configuration. Use immutable snapshot fields only on run records.

### Acceptance criteria
- editable newsletters reference canonical entities, not duplicate strings
- runs store immutable snapshots of resolved names and versions
- deletion flows use dependency checks rather than silent drift

## 6.14 P1 — The AI generation layer only supports a hardcoded provider set

**Type:** Extensibility blocker / runtime inconsistency  
**Evidence:** `backend/app/ai_generation.py:26`, `backend/app/ai_generation.py:169-183`

### What happens
Even if provider records were extended, runtime generation only supports a fixed set of providers.

### User impact
Adding providers through the UI is impossible unless backend generation logic is also manually extended.

### Required fix
Move generation to adapter-based execution. Runtime should resolve provider behavior from the provider instance adapter, not a hardcoded set.

### Acceptance criteria
- runtime generation dispatches by adapter key
- adding provider presets does not require editing a hardcoded `SUPPORTED_PROVIDERS` constant
- OpenAI-compatible providers can ride through a generic adapter

## 6.15 P2 — Template preview cannot be used before first save

**Type:** UX flow issue  
**Evidence:** `frontend/src/features/templates/EmailTemplatesPage.tsx:198-209`, `frontend/src/features/templates/EmailTemplatesPage.tsx:279-306`

### What happens
The preview UI is only available for an existing template record. New templates cannot be previewed before they are saved.

### User impact
Users are forced to persist incomplete or low-quality templates just to test them.

### Required fix
Allow local preview before first save, then adapter-based preview after save.

### Acceptance criteria
- unsaved templates can preview locally in the editor
- save is not required just to see render output

## 6.16 P2 — Provider and secret validation are only available after save

**Type:** UX flow issue  
**Evidence:** `frontend/src/features/providers/ProvidersPage.tsx:200-331`, `frontend/src/features/api-keys/ApiKeysPage.tsx:203-304`

### What happens
Users must create a provider or API key record before they can test it.

### User impact
The database fills with partially configured or invalid records.

### Required fix
Support draft validation before save.

### Acceptance criteria
- create flow can validate without persistence
- users can cancel invalid attempts without leaving residue data behind

## 6.17 P2 — Newsletter editor is a single overloaded form

**Type:** UX / cognitive overload  
**Evidence:** `frontend/src/features/newsletters/NewsletterEditorPage.tsx:259-536`

### What happens
The newsletter editor mixes content, provider config, credentials, template selection, delivery, scheduling, notes, and recipient import into one long form.

### User impact
The user has no mental grouping of setup stages and no guided progression.

### Required fix
Replace with a step-based authoring flow with preflight and inline blockers.

### Acceptance criteria
- steps are separated by task
- step completion states are visible
- invalid setup is surfaced before review/send

## 6.18 P2 — Scheduling UX is raw cron-first

**Type:** UX  
**Evidence:** `frontend/src/features/newsletters/NewsletterEditorPage.tsx:485-505`

### What happens
Scheduling is a raw cron input plus a checkbox.

### User impact
This is too low-level for most operators and makes “next run” hard to understand.

### Required fix
Provide a human schedule builder and an advanced cron escape hatch.

### Acceptance criteria
- common schedules are selectable without cron knowledge
- next run preview is shown in the selected timezone
- cron remains available under advanced settings only

## 6.19 P2 — Audience management is limited to pasted recipient lists

**Type:** Product gap  
**Evidence:** `backend/app/api/newsletters.py:116-185`, `frontend/src/features/newsletters/NewsletterEditorPage.tsx:508-519`

### What happens
Recipients are imported as raw text inside the newsletter editor. There is no reusable audience abstraction.

### User impact
Operators cannot maintain audiences cleanly across newsletters.

### Required fix
Create audience, contacts, segments, and suppression surfaces.

### Acceptance criteria
- audiences can be reused
- segments can be defined independently of newsletters
- recipient import is not embedded as a raw textarea in the editor

## 6.20 P2 — No public subscribe flow exists

**Type:** Product gap  
**Evidence:** `backend/app/api/public.py` only exposes unsubscribe handling

### What happens
The product supports unsubscribe, but not a public subscribe flow.

### User impact
Audience acquisition is outside the product.

### Required fix
Add subscription forms and optional double opt-in.

### Acceptance criteria
- at least one public subscribe flow exists
- audit and suppression behavior are preserved
- topic or list selection is supported

## 6.21 P2 — Operations UI is present but too raw to be trustworthy

**Type:** UX / observability gap  
**Evidence:** `frontend/src/features/dashboard/RunDashboardPage.tsx`

### What happens
The run dashboard is a basic list/detail view. It has no system-health context, no grouped issues, no strong troubleshooting affordances, and no audit surface.

### User impact
Operators still need logs or code-level context.

### Required fix
Add health dashboard, run-stage visualization, grouped failures, and remediation affordances.

### Acceptance criteria
- operators can diagnose common send and reconciliation failures from the UI alone
- audit events are visible
- delivery and scheduler health are obvious

## 6.22 P2 — `last_used_at` is exposed but not meaningfully maintained

**Type:** Observability integrity  
**Evidence:** `backend/app/models.py:85`, `backend/app/api/api_keys.py:63`

### What happens
The product displays `last_used_at`, but the review found no clear end-to-end update path ensuring it is reliably written on successful use.

### User impact
The UI suggests operational insight that may not be accurate.

### Required fix
Update usage metadata whenever secrets are successfully used for generation or delivery.

### Acceptance criteria
- successful generation updates AI secret last-used timestamp
- successful delivery updates delivery secret last-used timestamp
- validation updates last-validated timestamp, not last-used timestamp

## 6.23 P2 — Help tooltip accessibility is incomplete

**Type:** Accessibility  
**Evidence:** `frontend/src/features/newsletters/NewsletterEditorPage.tsx:541-567`

### What happens
The help icon is made focusable with `role="button"` and `tabIndex=0`, but there is no keyboard activation handler for Enter or Space.

### User impact
Keyboard users get a degraded experience.

### Required fix
Use an actual button element or add keyboard handlers and ARIA state.

### Acceptance criteria
- help affordances are keyboard-operable
- focus order and labels are clear
- screen-reader behavior is validated

## 6.24 P2 — Custom HTML preview is rendered directly into the DOM

**Type:** Security / robustness  
**Evidence:** `frontend/src/features/templates/EmailTemplatesPage.tsx:293-296`, `frontend/src/features/newsletters/NewsletterPreviewPage.tsx:154-155`

### What happens
Template and newsletter previews use `dangerouslySetInnerHTML`.

### Why this matters
For a trusted single-admin environment this may be tolerable, but it is not a safe long-term pattern for multi-user collaboration or imported template content.

### Required fix
Render previews inside a sandboxed iframe or sanitize aggressively, depending on future trust model.

### Acceptance criteria
- preview surface is isolated from the application shell
- unsafe markup cannot compromise the admin UI

---

## 7. What is missing from the product

This section focuses on missing user stories and missing product capabilities, not just bugs.

## 7.1 Onboarding and setup stories

Missing stories:

- As a new admin, I can see a setup checklist with blockers.
- As a new admin, I can validate my provider before saving it permanently.
- As a new admin, I can discover models right after connecting a provider.
- As a new admin, I can understand what is required before a live send.
- As a new admin, I can reach a “ready to send” state without reading docs or guessing.

## 7.2 Provider and model stories

Missing stories:

- As an admin, I can connect multiple instances of the same provider.
- As an admin, I can use a generic OpenAI-compatible endpoint.
- As an admin, I can manually add models when the upstream does not expose model discovery.
- As an admin, I can enable only approved models.
- As an admin, I can see provider health, last validated, and last discovered.

## 7.3 Secret-management stories

Missing stories:

- As an operator, I can store a secret without deciding its UI semantics first.
- As an operator, I can rotate a secret without manually re-entering every dependent configuration.
- As an operator, I can see where a secret is used.
- As an operator, I can distinguish active, inactive, invalid, and never-validated secrets.
- As an operator, I can reference environment or external-vault secrets.

## 7.4 Template stories

Missing stories:

- As an editor, I can start from a gallery of native templates.
- As an editor, I can duplicate a system template into a custom variant.
- As an editor, I can preview my template before saving it.
- As an editor, I can see supported variables and sample values.
- As an editor, I can version and roll back templates.
- As an editor, I can see which newsletters use a template before changing or archiving it.

## 7.5 Newsletter-authoring stories

Missing stories:

- As an editor, I can duplicate a newsletter.
- As an editor, I can autosave drafts.
- As an editor, I can see unsaved changes warnings.
- As an editor, I can preview with real merge data.
- As an editor, I can run a preflight checklist before sending.
- As an editor, I can see why send is disabled.
- As an editor, I can schedule without writing cron.
- As an editor, I can see the next run time in the correct timezone.
- As an editor, I can safely test-send without ambiguity about live provider readiness.

## 7.6 Audience stories

Missing stories:

- As an operator, I can import subscribers via CSV.
- As an operator, I can export subscribers and suppression status.
- As an operator, I can manage reusable segments.
- As an operator, I can see unsubscribe history.
- As an operator, I can manage list-level or topic-level preferences.
- As a subscriber, I can subscribe through a public endpoint or widget.
- As a subscriber, I can manage preferences instead of only unsubscribing globally.

## 7.7 Delivery stories

Missing stories:

- As an operator, I can define a delivery profile with sender defaults.
- As an operator, I can verify domain or sender identity status.
- As an operator, I can see webhook health.
- As an operator, I can retry failed deliveries or reconciliation.
- As an operator, I can see live delivery status without reading logs.

## 7.8 Operations stories

Missing stories:

- As an operator, I can see system health in one screen.
- As an operator, I can view audit history.
- As an operator, I can see scheduler health and next jobs.
- As an operator, I can distinguish generation failures from delivery failures.
- As an operator, I can see a run’s exact resolved provider, model, template version, and delivery profile.
- As an operator, I can see when a run used fallback behavior.
- As an operator, I can replay or retry failed steps safely.

## 7.9 Collaboration stories (later phase but important)

Not required for the immediate rebuild, but strategically valuable:

- As an admin, I can assign roles (admin, editor, operator, viewer).
- As an editor, I can submit a newsletter for approval.
- As a reviewer, I can approve or reject before send.
- As an operator, I can trace who changed a provider, template, or newsletter.

---

## 8. Product principles for the rebuild

These should govern every architectural and UX decision.

1. **One source of truth per concept.**  
   A provider model list cannot come from three places. A newsletter cannot store both a live relational reference and a mutable denormalized key for the same concept.

2. **Task-centric UX, not field-centric forms.**  
   Organize around connect, validate, discover, choose, preview, send, observe.

3. **Secrets must be secrets.**  
   A credential page is a vault, not a provider setup surface.

4. **No fake success.**  
   Validation, preview, and test flows must clearly distinguish local preview from real provider success.

5. **Preview must match runtime.**  
   One rendering engine, one variable schema.

6. **Unsafe actions require explicit context.**  
   Sending, deleting in-use templates, rotating secrets, or disabling providers should always explain consequences.

7. **Extensibility must be adapter-driven.**  
   New providers should not require touching validation enums, frontend dropdowns, runtime provider lists, and model catalogs in parallel.

8. **Self-hosted does not mean low-trust UX.**  
   Operators still expect polished setup, health, and recovery flows.

9. **Observability is part of the product.**  
   Audit, health, delivery events, and run snapshots are first-class features.

10. **Defer advanced builders until the registry is sound.**  
    Do not build drag-and-drop template tooling before templates, versions, and rendering are consistent.

---

## 9. Proposed target architecture

## 9.1 Bounded contexts

Pulse News should be restructured around the following domains:

1. **Secrets**
2. **AI Providers**
3. **Provider Models**
4. **Delivery Profiles**
5. **Templates**
6. **Newsletters**
7. **Audience**
8. **Runs and Audit**
9. **System Health**

## 9.2 Conceptual model

```text
Secret
 ├── used by ProviderInstance
 └── used by DeliveryProfile

ProviderInstance
 ├── belongs to AdapterPreset
 ├── references Secret
 └── has many ProviderModels

Template
 └── has many TemplateVersions

Audience
 ├── has many Contacts
 └── has many Segments

Newsletter
 ├── references ProviderInstance
 ├── references ProviderModel
 ├── references TemplateVersion
 ├── references DeliveryProfile
 ├── references AudienceSegment
 └── has many Runs

Run
 ├── stores immutable snapshot_json
 ├── has many RunEvents
 └── stores provider/delivery outcomes
```

## 9.3 Data model proposal

### 9.3.1 Secrets

```text
secrets
- id
- name
- secret_type
- provider_hint (nullable)
- source (db | env | external)
- ciphertext
- key_version
- is_active
- status
- last_validated_at
- last_used_at
- usage_count
- created_by
- created_at
- updated_at
```

### 9.3.2 Provider instances

```text
provider_instances
- id
- name
- adapter_key
- preset_key (nullable)
- secret_id
- enabled
- config_json
- default_model_id (nullable)
- health_status
- last_tested_at
- last_discovered_at
- discovery_state
- created_at
- updated_at
```

### 9.3.3 Provider models

```text
provider_models
- id
- provider_instance_id
- model_id
- label
- source (discovered | manual | seeded)
- capabilities_json
- context_window
- pricing_json
- is_enabled
- is_default
- is_deprecated
- last_seen_at
- created_at
- updated_at
```

### 9.3.4 Delivery profiles

```text
delivery_profiles
- id
- name
- provider_key
- secret_id
- enabled
- from_email
- from_name
- reply_to_email
- domain
- webhook_secret_id (nullable)
- health_status
- last_tested_at
- created_at
- updated_at
```

### 9.3.5 Templates and versions

```text
templates
- id
- slug
- name
- kind (system | custom)
- archived
- current_version_id
- created_at
- updated_at

template_versions
- id
- template_id
- version_number
- markup
- variable_schema_json
- preview_seed_data_json
- changelog
- created_by
- created_at
```

### 9.3.6 Audience

```text
contacts
- id
- email
- full_name
- status
- source
- created_at
- updated_at

audiences
- id
- name
- description
- created_at
- updated_at

audience_memberships
- id
- audience_id
- contact_id
- status

segments
- id
- audience_id
- name
- filter_json
- created_at
- updated_at

suppressions
- id
- contact_id
- scope (global | audience | newsletter | topic)
- reason
- created_at
```

### 9.3.7 Newsletters

```text
newsletters
- id
- name
- slug
- description
- status
- prompt_config_json
- provider_instance_id
- provider_model_id
- template_version_id
- delivery_profile_id
- audience_segment_id
- timezone
- schedule_rule_json
- notes
- created_at
- updated_at
```

### 9.3.8 Runs

```text
newsletter_runs
- id
- newsletter_id
- trigger_mode
- run_status
- snapshot_json
- preflight_json
- delivery_outcomes_json
- created_at
- updated_at

newsletter_run_events
- id
- run_id
- event_type
- event_status
- code
- message
- provider_id
- payload_json
- created_at
```

### 9.3.9 Audit

```text
audit_events
- id
- actor_email
- action
- entity_type
- entity_id
- summary
- payload_json
- created_at
```

## 9.4 The critical architectural rule

**Editable records should use canonical references. Immutable snapshots belong on runs, not on live newsletter configuration.**

That means:

- newsletters should not store loose `provider_name` and `template_key`
- runs **should** store resolved snapshot names and config details for reproducibility

---

## 10. Information architecture and navigation

## 10.1 Recommended top-level navigation

- Dashboard
- Newsletters
- Templates
- Audience
- AI Providers
- Secrets
- Delivery
- Runs
- Audit
- Settings / Health

## 10.2 Navigation rationale

### Dashboard
Overview of setup completeness, system health, recent runs, recent failures, and next scheduled sends.

### Newsletters
List, duplicate, draft, review, preview, send, schedule.

### Templates
System and custom templates in one gallery with versions.

### Audience
Contacts, lists, segments, suppressions, imports.

### AI Providers
Connection setup, discovery, model enablement, health.

### Secrets
Central vault for credentials, detached from provider UX.

### Delivery
Resend now; adapter-ready for more providers later.

### Runs
Execution history, outcomes, reconciliation, retries.

### Audit
Operator-visible change history.

### Settings / Health
Environment diagnostics, scheduler health, webhook health, system version, backup/export guidance.

## 10.3 First-run onboarding

The app should include an onboarding checklist visible on the dashboard until complete:

1. Create first secret
2. Add first AI provider
3. Validate provider
4. Discover models
5. Add delivery profile
6. Validate sender identity / domain
7. Create first template or choose a native template
8. Create sample newsletter
9. Run preflight
10. Send test newsletter

Each item should show one of:

- not started
- blocked
- warning
- ready
- complete

---

## 11. Provider strategy

## 11.1 Do not keep adding hardcoded providers

The current approach does not scale. Provider support must be adapter-driven.

## 11.2 Recommended adapter strategy

Use a hybrid approach:

1. **Native adapters** for major providers with custom auth or model semantics.
2. **OpenAI-compatible adapter** for providers that can be handled by base URL + API key + model naming conventions.
3. **Provider presets** so users can add known providers quickly without hand-typing base URLs.

This gives the product both breadth and maintainability.

## 11.3 First-wave provider list

The first provider shortlist should be:

1. OpenAI
2. OpenAI-compatible custom endpoint
3. Anthropic
4. Azure OpenAI
5. Google AI / Gemini
6. Vertex AI
7. Bedrock
8. OpenRouter
9. Ollama / LM Studio
10. Z.AI
11. Kimi (kimi.com / Moonshot AI)

### Why Z.AI and Kimi belong in the first list
Both are strong candidates for early support because their official documentation exposes OpenAI-compatible integration patterns:

- Z.AI explicitly documents compatibility with the OpenAI SDK by changing API key and base URL.
- Kimi’s API quickstart explicitly shows usage via the OpenAI SDK and states compatibility with the OpenAI API format.

That means they can ship early as either:
- named presets on top of the generic OpenAI-compatible adapter, or
- thin dedicated adapters if later capability-specific behavior justifies it.

## 11.4 Delivery provider strategy

Keep **Resend** as the first delivery provider, but architect delivery to support expansion later:

- Resend
- Postmark
- Amazon SES
- Mailgun
- SMTP relay

The delivery layer should use the same adapter/preset principles as the AI provider layer.

## 11.5 Suggested provider adapter contract

```python
class ProviderAdapter(Protocol):
    key: str
    display_name: str
    supports_model_discovery: bool

    def auth_schema(self) -> dict: ...
    def config_schema(self) -> dict: ...
    def validate_config(self, config: dict) -> ValidationResult: ...
    def test_connection(self, secret: SecretRef, config: dict) -> ConnectionTestResult: ...
    def discover_models(self, secret: SecretRef, config: dict) -> list[DiscoveredModel]: ...
    def normalize_model_identifier(self, model_id: str) -> str: ...
    def completion(self, request: CompletionRequest) -> CompletionResponse: ...
```

## 11.6 Suggested provider preset metadata

```json
{
  "preset_key": "zai",
  "display_name": "Z.AI",
  "adapter_key": "openai_compatible",
  "default_base_url": "https://api.z.ai/api/paas/v4/",
  "secret_type": "bearer",
  "supports_model_discovery": false,
  "recommended_models": ["glm-5", "glm-5.1", "glm-4.5-air"]
}
```

```json
{
  "preset_key": "kimi",
  "display_name": "Kimi",
  "adapter_key": "openai_compatible",
  "default_base_url": "https://api.kimi.com/coding/v1",
  "secret_type": "bearer",
  "supports_model_discovery": false,
  "recommended_models": ["kimi-k2.5"]
}
```

The exact recommended model list should remain server-delivered metadata, not hardcoded in the frontend.

---

## 12. Detailed implementation roadmap

The plan below is intentionally sequenced. Earlier phases reduce risk and remove structural blockers for later phases.

## Phase 0 — Correctness and security stabilization

**Goal:** Stop data loss, silent fallback, and fake readiness states before any large UI redesign.

### Backend work

1. Change provider update semantics.
   - Implement `PATCH` semantics or preserve unspecified fields on update.
   - Prevent nulling `configuration` unless explicitly requested.

2. Enforce cross-entity newsletter validation.
   - Validate provider instance existence and enablement.
   - Validate selected model against provider instance.
   - Validate template existence.
   - Validate delivery configuration.
   - Validate secret compatibility.

3. Eliminate template reference drift.
   - Introduce canonical template reference strategy.
   - Block deletion of in-use templates or force reassignment.
   - Remove silent template fallback for missing custom templates.

4. Align test-send and real-send rules.
   - Test send must reflect live prerequisites.
   - Explicitly surface preview-only mode as non-live.

5. Fix run reconciliation.
   - Store delivery context on runs.
   - Reconcile using the exact sent-with profile or secret.

6. Encrypt secrets at rest.
   - Introduce new encrypted secrets table or migrate current one in place with versioning.
   - Support master-key rotation path.

7. Update usage metadata.
   - Write `last_used_at` after successful generation or delivery.
   - Write `last_validated_at` after successful validation.

8. Unify preview/runtime template rendering.
   - One render engine.
   - One variable schema.
   - Fix `newsletter_name` mismatch.

### Frontend work

1. Disable destructive provider toggles until the backend fix lands.
2. Remove or relabel fake success states.
3. Add blocker messages on send/test surfaces.
4. Add destructive-action confirmations where behavior can affect live newsletters.

### Tests

- provider toggle preserves configuration
- deleting in-use template is blocked or requires reassignment
- newsletter creation fails for mismatched provider/model/secret combinations
- provider test fails for invalid upstream config
- secret test fails for invalid secret
- preview and runtime render the same output for the same template data
- reconciliation uses correct delivery credentials
- last-used timestamps update on successful usage

### Definition of done

- no silent destructive partial update
- no secret plaintext persistence
- no fake “working” test results
- no silent template fallback for deleted custom templates

---

## Phase 1 — Information architecture and navigation redesign

**Goal:** Make the product understandable before making it visually sophisticated.

### Frontend work

1. Reorganize top-level navigation.
2. Rename **API Keys** to **Secrets**.
3. Create separate **AI Providers** and **Delivery** sections.
4. Add dashboard checklist.
5. Rework empty states to guide the next action.

### Product behavior changes

1. Provider setup no longer happens in the newsletter editor.
2. Delivery setup no longer happens through newsletter-level Resend key selection.
3. Template selection becomes preview-first and gallery-first.

### Definition of done

A first-time admin can identify where to configure:
- secrets
- AI providers
- delivery
- templates
- newsletters
- runs

without inference or code knowledge.

---

## Phase 2 — Provider registry and model management

**Goal:** Replace the hardcoded provider system with an adapter-driven provider platform.

### Backend work

1. Implement provider adapter registry.
2. Implement provider preset registry.
3. Add adapter metadata endpoint for frontend form generation.
4. Add provider instance CRUD.
5. Add connection validation endpoint.
6. Add model discovery endpoint.
7. Add manual model add/update/delete endpoints.
8. Persist provider-model catalog per instance.

### Suggested endpoints

```text
GET    /provider-adapters
GET    /provider-presets
POST   /provider-instances
PATCH  /provider-instances/{id}
POST   /provider-instances/{id}/validate
POST   /provider-instances/{id}/discover-models
GET    /provider-instances/{id}/models
PATCH  /provider-instances/{id}/models/{model_id}
POST   /provider-instances/{id}/models
```

### Frontend work

1. Provider catalog page with search and provider cards.
2. “Add provider” wizard:
   - choose provider preset or generic adapter
   - choose secret
   - fill config
   - validate
   - discover models
   - enable models
   - choose default

3. Provider detail page:
   - health state
   - last validation
   - last discovery
   - enabled models
   - secret usage
   - audit history

### Definition of done

Adding a provider does not require:
- hardcoding a new frontend dropdown option
- editing a backend enum
- editing runtime provider dispatch separately
- maintaining multiple static model catalogs

---

## Phase 3 — Secrets redesign

**Goal:** Turn credentials into a real secret-management surface.

### Backend work

1. Introduce `secrets` model and migration.
2. Add encryption and key-version support.
3. Add validation records.
4. Add usage graph queries.
5. Add rotation endpoint.
6. Add optional env/external secret references.

### Suggested endpoints

```text
GET    /secrets
POST   /secrets
GET    /secrets/{id}
PATCH  /secrets/{id}
POST   /secrets/{id}/validate
POST   /secrets/{id}/rotate
GET    /secrets/{id}/usage
```

### Frontend work

1. Secrets list page:
   - type
   - hint
   - status
   - last validated
   - last used
   - usage count

2. Secret create page:
   - neutral secret types
   - provider hint optional
   - no provider-model dropdowns

3. Secret detail page:
   - masked display
   - usage references
   - rotation
   - deactivation
   - audit events

### Definition of done

The user can think about secrets independently from provider configuration.

---

## Phase 4 — Template registry and template authoring

**Goal:** Make templates a first-class product capability.

### Backend work

1. Seed system templates into canonical DB registry.
2. Introduce template versions.
3. Introduce template usage graph.
4. Introduce canonical variable schema.
5. Unify preview/runtime rendering.
6. Add clone/duplicate and archive endpoints.

### Suggested endpoints

```text
GET    /templates
POST   /templates
GET    /templates/{id}
PATCH  /templates/{id}
POST   /templates/{id}/clone
POST   /templates/{id}/archive
GET    /templates/{id}/versions
POST   /templates/{id}/versions
POST   /templates/{id}/preview
GET    /templates/{id}/usage
```

### Frontend work

1. Template gallery:
   - system + custom
   - thumbnail
   - tags
   - description
   - usage count
   - last updated

2. Template detail:
   - preview
   - variable schema
   - version history
   - duplicate
   - archive

3. Template editor:
   - split code/preview view
   - preview before save
   - variable inspector
   - linting
   - seed data presets

### Definition of done

Every selectable template is:
- visible
- previewable
- versioned
- clonable
- traceable to newsletters that use it

---

## Phase 5 — Newsletter authoring rebuild

**Goal:** Replace the overloaded form with a guided, trustworthy authoring workflow.

### New step structure

1. **Basics**
   - name
   - slug
   - description
   - status

2. **Content**
   - prompt strategy
   - tone / style presets
   - draft subject / preheader strategy
   - generation settings

3. **AI**
   - provider instance
   - model
   - generation preview
   - validation status

4. **Template**
   - gallery
   - preview
   - variables preview

5. **Audience**
   - audience / segment
   - estimated recipient count
   - suppression summary

6. **Delivery**
   - delivery profile
   - sender identity
   - live test capability

7. **Schedule**
   - human-friendly schedule builder
   - timezone
   - next run preview
   - advanced cron override

8. **Review**
   - preflight checklist
   - resolved dependencies
   - warnings
   - send or schedule

### Backend work

1. Introduce preflight endpoint.
2. Introduce newsletter duplicate endpoint.
3. Introduce draft autosave semantics.
4. Introduce review-state model if approvals are added later.
5. Use canonical references only.

### Suggested endpoints

```text
GET    /newsletters
POST   /newsletters
GET    /newsletters/{id}
PATCH  /newsletters/{id}
POST   /newsletters/{id}/duplicate
GET    /newsletters/{id}/preflight
POST   /newsletters/{id}/generate
POST   /newsletters/{id}/preview
POST   /newsletters/{id}/test-send
POST   /newsletters/{id}/send
```

### Frontend work

1. Step-based editor.
2. Autosave.
3. Unsaved changes prompt.
4. Duplicate newsletter.
5. Inline blockers with remediation links.
6. Recipient count and send confirmation modal.
7. No direct AI secret dropdown in authoring unless in advanced override mode.

### Definition of done

A user can move from draft to send without guessing what is missing.

---

## Phase 6 — Delivery, audience, and operations surfaces

**Goal:** Make the platform operable without log diving.

### Delivery work

1. Delivery adapter abstraction.
2. Resend profile support first.
3. Sender and domain verification UI.
4. Webhook health UI.
5. Retry/reconcile tooling.

### Audience work

1. Contacts and audiences.
2. Segment builder.
3. CSV import/export.
4. Suppression list.
5. Preference center groundwork.
6. Public subscribe endpoint and widgets.

### Operations work

1. Health dashboard.
2. Audit log UI.
3. Run-stage timeline.
4. Recent failures panel.
5. Provider health panel.
6. Delivery health panel.
7. Scheduler status view.
8. Retry and replay affordances where safe.

### Definition of done

An operator can answer:
- Is the system healthy?
- What failed?
- Why did it fail?
- What exactly was used for the run?
- What should I do next?

from the product UI alone.

---

## Phase 7 — Migration, hardening, and rollout

**Goal:** Move safely from the current architecture to the target architecture.

### Migration work

1. Backfill system templates into DB.
2. Migrate template references to canonical IDs or version IDs.
3. Migrate plaintext API keys to encrypted secrets.
4. Create provider instances from existing provider rows.
5. Create delivery profiles from existing Resend configuration.
6. Backfill run snapshots with as much delivery/provider context as possible.
7. Produce a migration validation report.

### Compatibility strategy

1. Add new schema and services first.
2. Read through compatibility layer.
3. Migrate data.
4. Update frontend to new APIs.
5. Remove legacy fields only after data verification.

### Rollout safeguards

- feature flags if needed
- migration dry-run command
- validation report command
- rollback plan for schema-only changes
- audit of in-use templates and newsletters before destructive migrations

### Definition of done

Legacy duplicated fields and hardcoded catalogs can be removed without loss of fidelity.

---

## 13. Detailed UX requirements by area

## 13.1 Secrets page requirements

- must not ask for provider models
- must not force provider-specific UX unnecessarily
- must show status and usage
- must support rotate/deactivate
- must never expose full secret after creation

## 13.2 Provider page requirements

- must support multiple instances of same provider
- must support validation before save
- must support model discovery
- must show discovery source and timestamp
- must allow manual model curation
- must show health status
- must surface errors, not raw exceptions

## 13.3 Template page requirements

- must include system templates
- must support duplicate/clone
- must support preview before save
- must support version history
- must show where a template is used
- must validate merge variables
- must ensure preview equals runtime

## 13.4 Newsletter editor requirements

- must be step-based
- must autosave
- must show preflight
- must disable send when blocked
- must explain blockers
- must show recipient count
- must show exact resolved provider/model/template/delivery profile before send

## 13.5 Audience requirements

- reusable audiences
- reusable segments
- imports with validation feedback
- suppression visibility
- subscription acquisition flow
- unsubscribe and preferences history

## 13.6 Operations requirements

- health overview
- audit visibility
- run stage events
- delivery reconciliation visibility
- retry where safe
- scheduler visibility
- webhook visibility

---

## 14. What not to do yet

These are important non-goals for the current rebuild sequence.

1. Do not add many more hardcoded provider types on top of the current design.
2. Do not build a drag-and-drop template builder before templates are normalized and versioned.
3. Do not keep provider setup logic inside the secret-management surface.
4. Do not let newsletters continue to store duplicate provider/template identifiers as live editable state.
5. Do not treat local preview or simulated send as equivalent to a live provider validation.
6. Do not add major new UI polish before correctness and trust are fixed.

---

## 15. Acceptance criteria for the rebuilt platform

The rebuild can be considered successful only when all of the following are true:

### Trust and correctness
- toggling a provider never destroys configuration
- preview output matches runtime output
- test states correspond to real upstream readiness
- no silent template fallback changes live output unexpectedly

### Security
- secrets are encrypted at rest
- secret rotation is supported
- usage metadata is real, not decorative
- full secret values are not retrievable after creation

### UX
- new admins can complete setup from a guided checklist
- provider/model setup is understandable without code knowledge
- newsletter authoring is step-based and blocker-driven
- templates are previewable, versioned, and clonable
- send/schedule affordances are explicit and safe

### Extensibility
- new provider presets can be added without editing multiple hardcoded lists
- OpenAI-compatible providers can be added quickly
- delivery providers can expand without reworking newsletter entities

### Operations
- operators can diagnose run failures from the UI
- audit history is visible
- scheduler and webhook health are visible
- run snapshots are reproducible and immutable

---

## 16. Starter issue backlog

Below is the initial issue set that should be created immediately.

### EPIC 1 — Stabilization
- PN-001: Preserve provider configuration on toggle/update
- PN-002: Block or migrate deletion of in-use templates
- PN-003: Enforce newsletter cross-entity validation
- PN-004: Encrypt secrets at rest
- PN-005: Align test-send with live-send requirements
- PN-006: Fix reconciliation to use snapshot delivery context
- PN-007: Unify preview/runtime template rendering
- PN-008: Fix `newsletter_name` merge behavior

### EPIC 2 — Domain normalization
- PN-009: Introduce secrets model
- PN-010: Introduce provider instances and provider model catalog
- PN-011: Introduce delivery profiles
- PN-012: Introduce template versions
- PN-013: Remove newsletter duplicate provider/template live fields
- PN-014: Add run snapshot schema

### EPIC 3 — Provider platform
- PN-015: Build provider adapter registry
- PN-016: Build provider preset registry
- PN-017: Build provider validation flow
- PN-018: Build model discovery flow
- PN-019: Add OpenAI-compatible adapter
- PN-020: Add Z.AI preset
- PN-021: Add Kimi preset

### EPIC 4 — Template platform
- PN-022: Seed system templates into DB
- PN-023: Build template gallery
- PN-024: Build template usage graph
- PN-025: Build version history
- PN-026: Add duplicate/clone flow
- PN-027: Add pre-save local preview

### EPIC 5 — Authoring UX
- PN-028: Replace newsletter long form with step-based editor
- PN-029: Add autosave
- PN-030: Add preflight endpoint and UI
- PN-031: Add duplicate newsletter
- PN-032: Add human-friendly schedule builder
- PN-033: Add send confirmation modal

### EPIC 6 — Audience and operations
- PN-034: Introduce audiences and segments
- PN-035: Build CSV import/export
- PN-036: Add public subscribe flow
- PN-037: Build health dashboard
- PN-038: Build audit UI
- PN-039: Build provider/delivery health panels
- PN-040: Build retry and reconciliation tooling UI

---

## 17. Risk register and mitigations

## 17.1 Migration risk
**Risk:** Existing newsletters may rely on duplicate fields or silent fallback behavior.  
**Mitigation:** Add compatibility layer, migration report, and dependency checks before field removal.

## 17.2 Secret encryption rollout risk
**Risk:** Incorrect key management can lock users out of stored secrets.  
**Mitigation:** Use versioned encryption keys, migration dry-run, and backup/export guidance.

## 17.3 Provider adapter sprawl
**Risk:** Adding too many bespoke adapters too early will recreate the current problem.  
**Mitigation:** Use generic OpenAI-compatible adapter plus presets wherever possible.

## 17.4 Template trust mismatch
**Risk:** Preview and runtime continue diverging if separate renderers remain.  
**Mitigation:** One render engine, one variable schema, one preview path.

## 17.5 Product scope creep
**Risk:** Team tries to solve advanced design-builder or collaboration features before fundamentals.  
**Mitigation:** Keep the phased plan strict. Stabilization and normalization come first.

---

## 18. Recommended immediate next step

The next practical move is to turn **Phase 0** and **Phase 1** into concrete GitHub issues and begin with the correctness/security work before any larger redesign branch.

The exact recommended first sequence is:

1. fix destructive provider update behavior
2. fix template reference integrity
3. encrypt secrets
4. remove fake validation states
5. unify preview/runtime rendering
6. introduce canonical architecture for secrets/providers/templates
7. rebuild navigation around the new structure

---

## 19. Appendix A — Current anti-pattern map

This is the shortest way to describe the current architecture problem:

### Competing provider truths
- `SupportedProvider` enum in schema
- `SUPPORTED_PROVIDERS` in runtime generation
- provider types list in provider UI
- provider types list in API key UI

### Competing model truths
- backend provider model catalog
- frontend provider model catalog
- provider configuration JSON `models`
- newsletter-selected `model_name`

### Competing template truths
- database templates
- built-in `signal` and `ledger` runtime fallback
- newsletter `template_key`
- newsletter `template_id`

### Competing credential truths
- provider-specific API key records
- environment provider keys
- per-newsletter resend override
- environment resend configuration

The rebuild must eliminate these competing truths.

---

## 20. Appendix B — Suggested preflight response shape

```json
{
  "status": "blocked",
  "checks": [
    {
      "code": "provider.not_validated",
      "status": "warning",
      "message": "Provider has never been validated.",
      "resolution_path": "/providers/12"
    },
    {
      "code": "delivery.missing_sender",
      "status": "blocked",
      "message": "Delivery profile has no verified sender.",
      "resolution_path": "/delivery/3"
    }
  ],
  "resolved": {
    "provider_instance_id": 12,
    "provider_name": "Kimi",
    "model_id": "kimi-k2.5",
    "template_version_id": 44,
    "delivery_profile_id": 3,
    "audience_segment_id": 7
  },
  "recipient_count": 1421
}
```

---

## 21. Appendix C — Why OpenCode and LiteLLM are useful reference points

Pulse News should not copy another product’s UX blindly, but two implementation patterns are worth borrowing:

1. **OpenCode-style separation of credentials from provider configuration.**  
   This is a clean mental model: connect credentials, then configure providers.

2. **LiteLLM-style normalization for OpenAI-compatible providers.**  
   This drastically reduces the work required to support providers that are already compatible with the OpenAI SDK or OpenAI-style HTTP interfaces.

The point is not imitation. The point is using proven patterns that reduce maintenance cost and make expansion sane.

---

## 22. References

1. OpenCode provider documentation: <https://opencode.ai/docs/providers/>  
   Relevant point: credentials are handled separately from provider configuration, and provider config supports custom base URLs.

2. LiteLLM OpenAI-compatible endpoints: <https://docs.litellm.ai/docs/providers/openai_compatible>  
   Relevant point: a generic OpenAI-compatible route allows many providers to be supported with base URL + API key metadata.

3. Z.AI official OpenAI SDK compatibility guide: <https://docs.z.ai/guides/develop/openai/python>  
   Relevant point: Z.AI explicitly supports OpenAI SDK-compatible integration and documents a base URL of `https://api.z.ai/api/paas/v4/`.

4. Z.AI API introduction: <https://docs.z.ai/api-reference/introduction>  
   Relevant point: Z.AI documents standard HTTP API usage and bearer-token authentication.

5. Kimi API quickstart: <https://platform.kimi.ai/docs/guide/start-using-kimi-api>  
   Relevant point: Kimi’s official quickstart shows usage through the OpenAI SDK with `https://api.kimi.com/coding/v1` and states that the API is fully compatible with the OpenAI API format.

6. Kimi API overview: <https://platform.kimi.ai/docs/overview>  
   Relevant point: Kimi exposes a formal API platform and documented model access.

7. Kimi official site: <https://www.kimi.com/en>  
   Relevant point: confirms the `kimi.com` product surface and brand.

---

## 23. Final position

Pulse News does not need another round of superficial UI patching. It needs a coherent product model.

The rebuild should make the system:

- secure enough to trust with credentials
- modular enough to add providers without collateral edits
- clear enough that a new operator can set it up without reverse-engineering
- safe enough that preview, test, send, and reconciliation are honest
- observable enough that operations do not require reading application code

That is the bar.
