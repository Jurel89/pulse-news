# Pulse News — Full Fix and Improvement Review

## Purpose

This document turns the code review into an implementation-ready remediation plan for **Pulse News**, a self-hosted AI newsletter platform.

The goal is not to propose a product rewrite. The goal is to make the current codebase **correct, reliable, auditable, and operationally safe** while keeping the overall architecture simple.

---

## Review basis

### Repository areas reviewed

- `backend/app/**`
- `backend/tests/**`
- `frontend/src/**`
- `Dockerfile`
- `backend/pyproject.toml`
- `.planning/**`

### Verification performed

1. Static review of backend, frontend, scheduler, delivery, auth, and planning documents.
2. Frontend build verification:
   - `npm ci`
   - `npm run build`
   - Result: **passes**.
3. Backend test verification:
   - On the unmodified code in the local verification environment, `pytest` aborts during app import because of the `DELETE /api/newsletters/{id}` route definition.
   - In a **disposable analysis copy only**, after patching that one route so the app could start, the existing 6 backend tests passed.
4. Additional manual API exercises in the disposable copy confirmed several runtime defects that the current test suite does not cover.

### Important note about evidence

A few of the most important defects below were **confirmed empirically** in the disposable analysis copy:

- editing a newsletter from the list view can wipe recipients and reset `delivery_topic`
- archived newsletters can still be sent manually
- invalid cron schedules return `500` **after** persisting the bad row
- resuming a schedule with no cron sets `schedule_enabled=true`
- `date_to=YYYY-MM-DD` excludes runs from that day

---

## Executive summary

The project is a solid prototype, but it is **not yet production-safe** as a reliable newsletter system.

The largest problems are not missing features; they are **integrity failures**:

1. **The send lifecycle is not durable.** A real email send can happen before the run is recorded.
2. **The frontend and backend contracts are inconsistent.** This causes real data loss when editing from the newsletter list.
3. **Scheduling validation happens too late.** Invalid schedules are persisted and can break startup behavior.
4. **History is not trustworthy.** Run detail mixes snapshots with mutable current newsletter state.
5. **Compliance and suppression are incomplete.** `delivery_topic` is half-implemented, one-click unsubscribe headers are missing, and provider webhook/suppression workflows are absent.
6. **Security and deploy hardening are underpowered.** Bootstrap is weakly protected, migrations are missing, and production misconfiguration can silently degrade into local-preview behavior.

If you want the shortest path to a usable v1, the first implementation target should be:

- fix the startup blocker
- fix the frontend/backend contract mismatch
- fix send/run persistence order
- validate schedule state before commit
- block invalid send states
- complete unsubscribe/topic/delivery hardening

---

## Priority legend

- **P0** — must fix before trusting the app in production
- **P1** — high priority; correctness, operator trust, or major operational risk
- **P2** — important improvement; not necessarily blocking first production use

---

# P0 — Critical blockers

## P0-1. App startup/import blocker on delete route

**Severity:** P0  
**Area:** Backend routing / compatibility  
**Files:**
- `backend/app/api/newsletters.py:543-557`

### What is wrong

The delete route is declared as:

- `status_code=204`
- return type annotation `-> None`

In the local verification environment, FastAPI raises an assertion during route registration:

> `AssertionError: Status code 204 must not have a response body`

That prevents the backend app from importing cleanly, which means tests and runtime startup can fail depending on FastAPI version behavior.

### Why it matters

This is a hard blocker. If the app cannot register routes reliably, nothing else matters.

### Recommended fix

Make the route unambiguous:

- set `response_model=None`
- return `Response(status_code=204)` explicitly
- or remove inference entirely and use `response_class=Response`

Example target shape:

```python
from fastapi import Response

@newsletters_router.delete(
    "/{newsletter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_newsletter(...):
    ...
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

### Acceptance criteria

- backend imports cleanly
- `pytest` starts without route registration failure
- delete endpoint returns empty 204 response body consistently

---

## P0-2. Frontend/backend contract mismatch causes recipient and topic data loss

**Severity:** P0  
**Area:** API contract / frontend state / data integrity  
**Files:**
- `backend/app/schemas.py:48-69`
- `backend/app/api/newsletters.py:253-257`
- `frontend/src/lib/api.ts:152`
- `frontend/src/features/newsletters/newsletter-types.ts:1-29, 71-89`
- `frontend/src/App.tsx:48-55, 267-278`

### What is wrong

`GET /api/newsletters` returns `NewsletterSummary`, which does **not** include:

- `delivery_topic`
- `recipient_import_text`
- `recipients`

But the frontend types `api.listNewsletters()` as returning full `Newsletter[]` detail records and then uses those list items directly as editable objects.

The editor conversion logic expects detail-only fields:

- `delivery_topic`
- `recipient_import_text`

Those fields are missing in the actual list payload, so the form is populated with `undefined` / omitted values.

### Confirmed observed behavior

In the disposable analysis copy, taking the current list payload and saving it back through the update endpoint produced this result:

- `recipient_import_text` became `""`
- all recipients were deleted
- stored `delivery_topic` was reset to `default-topic`

This is a real data-loss bug.

### Why it matters

This is the most dangerous UX bug in the repo because it can silently destroy audience data and unsubscribe scope metadata through normal editing.

### Recommended fix

Pick one of these approaches and be consistent:

#### Preferred: split summary and detail types cleanly

- Keep `GET /api/newsletters` as a true summary endpoint.
- Create separate frontend types:
  - `NewsletterSummary`
  - `NewsletterDetail`
- When the user clicks **Edit**, fetch `GET /api/newsletters/{id}` first and only then open the editor.

#### Minimum safe fix

- add `delivery_topic` to `NewsletterSummary`
- do **not** reuse list responses as edit payloads
- fetch detail before edit

### Acceptance criteria

- editing from the list view does not change recipients unless the user changes the recipient field
- editing from the list view preserves `delivery_topic`
- list types and detail types are distinct in frontend code
- an automated regression test proves list-view edit does not wipe data

---

## P0-3. Send side effect happens before the run record exists

**Severity:** P0  
**Area:** Send lifecycle / auditability / duplicate prevention  
**Files:**
- `backend/app/api/newsletters.py:184-250`

### What is wrong

`execute_newsletter_send()` does this in the wrong order:

1. render newsletter
2. compute recipients
3. send email(s)
4. create `NewsletterRun`
5. store outcomes

That means a process crash or exception between steps 3 and 4 can create real outbound mail with no durable run record.

### Why it matters

A newsletter platform needs an **attempt record before the external side effect**. Otherwise:

- duplicate-send protection is weak
- audit history is incomplete
- scheduled/manual overlap cannot be reasoned about safely
- postmortem analysis becomes unreliable

### Recommended fix

Refactor the send lifecycle to a state machine:

1. create run row in `pending`
2. persist it and get a stable run ID / attempt key
3. render final content snapshot
4. store the rendered snapshot on the run
5. send using provider idempotency key derived from the run/attempt
6. update run to `sent`, `partial`, or `failed`
7. append recipient events and provider IDs

Suggested fields to add:

- `attempt_key` (unique)
- `started_at`
- `completed_at`
- `failure_reason`
- `rendered_subject`
- `rendered_preheader`
- `rendered_html`
- `rendered_plain_text`
- `snapshot_prompt`

### Acceptance criteria

- a run exists before any provider request is made
- provider send uses an idempotency key derived from the run
- rerunning the same attempt cannot create duplicate sends
- failed sends still leave a durable run record

---

## P0-4. Run snapshots are not trustworthy, and prompt leakage is possible

**Severity:** P0  
**Area:** Snapshot integrity / content safety  
**Files:**
- `backend/app/email_templates.py:19-23, 79-104`
- `backend/app/api/newsletters.py:132-161`
- `backend/app/ai_generation.py:42-69, 72-125`

### What is wrong

The render pipeline normalizes blank draft content like this:

- subject falls back to newsletter name
- preheader falls back to description
- body falls back to draft body or description or **prompt**

But the run snapshot stores raw draft fields from the newsletter row, not the final rendered values actually used for sending.

That creates two problems:

1. **History drift** — a run can show blank subject/body even though the real email used fallback content.
2. **Prompt leakage** — if `draft_body_text` is blank, the rendered/sent body can fall back to `newsletter.prompt`.

The local fallback generation path also embeds prompt text into the generated draft body.

### Why it matters

Internal prompts are operator instructions, not newsletter content. Leaking them into live mail is a severe correctness issue.

### Recommended fix

Never derive a run snapshot from mutable newsletter fields after the fact.

Store the exact content used:

- final subject
- final preheader
- final plain-text body
- final HTML
- template key actually rendered
- prompt snapshot used for generation
- provider/model used for generation and send

Also change fallback behavior:

- never use `newsletter.prompt` as send body fallback
- if there is no body content, block the send and return validation error
- generation fallback may reference the prompt internally, but should not produce prompt text verbatim in the user-facing body unless explicitly intended

### Acceptance criteria

- run detail shows exactly the content that was rendered and sent
- blank body cannot cause prompt text to be sent
- generation run snapshot includes the exact prompt used
- invalid template keys are rejected rather than silently coerced

---

## P0-5. Invalid schedule data is committed before validation, and bad rows persist after 500s

**Severity:** P0  
**Area:** Scheduling / transaction boundaries  
**Files:**
- `backend/app/api/newsletters.py:298-302, 489-493`
- `backend/app/scheduler.py:45-68`
- `backend/app/main.py:17-22`

### What is wrong

Create and update commit the newsletter row **before** calling `sync_newsletter_schedule()`.

If `CronTrigger.from_crontab()` raises because of bad cron or bad timezone, the API returns `500`, but the invalid row is already committed.

### Confirmed observed behavior

In the disposable analysis copy:

- creating a newsletter with `schedule_enabled=true` and `schedule_cron="bad cron"` returned `500 Internal Server Error`
- the invalid newsletter still appeared in the list afterward

### Why it matters

This causes a bad operator experience and can poison startup reconciliation because the scheduler reads persisted rows on boot.

### Recommended fix

#### Validation must happen before commit

Add server-side validation for:

- cron expression format
- timezone validity
- legal state combinations:
  - no `schedule_enabled=true` without a cron
  - archived newsletters cannot be scheduled
  - paused newsletters cannot be scheduled unless status is explicitly resumed

Return `422 Unprocessable Entity` with structured error details.

#### Startup safety

During startup reconciliation, a single bad row must not break scheduler initialization.

- catch invalid schedule rows
- log and mark them as invalid
- do not let one bad row stop the whole app

### Acceptance criteria

- invalid cron/timezone returns `422`, not `500`
- invalid schedule rows are not committed
- startup survives malformed schedule data already present in the DB
- tests cover invalid cron, invalid timezone, no-cron resume, archived+scheduled mismatch

---

## P0-6. Invalid send states are allowed

**Severity:** P0  
**Area:** Newsletter state machine / sending rules  
**Files:**
- `backend/app/api/newsletters.py:399-444, 497-540`
- `backend/app/scheduler.py:30-40`
- `backend/app/email_delivery.py:96-178`

### What is wrong

The app allows operationally invalid states:

- archived newsletters can still be sent manually
- paused newsletters can still be sent manually
- `schedule/resume` can set `schedule_enabled=true` even with no cron
- scheduled execution checks `schedule_enabled` + `schedule_cron`, but ignores newsletter `status`

### Confirmed observed behavior

In the disposable analysis copy:

- an archived newsletter still sent successfully via `POST /api/newsletters/{id}/send`
- `POST /api/newsletters/{id}/schedule/resume` succeeded even when `schedule_cron` was `null`
- an update could set `status="archived"` and `schedule_enabled=true`, and a scheduler job was created

### Why it matters

The product state model is currently inconsistent. Operators will eventually distrust the UI if archived or paused newsletters still run.

### Recommended fix

Introduce explicit rules:

- `draft` — preview/test/generate allowed, live send blocked
- `active` — live send allowed, schedule allowed
- `paused` — live send blocked, schedule disabled
- `archived` — live send blocked, schedule disabled

Enforce in API and scheduler.

For no-recipient state:

- block send with `400` or `422`
- do not create a normal sent run
- create a failed/no-op run only if you want history of the attempted action

### Acceptance criteria

- archived and paused newsletters cannot send
- no schedule can be resumed without valid cron
- archived newsletters cannot have active scheduler jobs
- zero-recipient sends are rejected explicitly

---

## P0-7. `delivery_topic` is broken end-to-end

**Severity:** P0  
**Area:** Compliance / unsubscribe scope  
**Files:**
- `backend/app/models.py:58-62`
- `backend/app/api/newsletters.py:279, 472`
- `backend/app/schemas.py:48-69, 83-109`
- `frontend/src/features/newsletters/newsletter-types.ts:1-49`
- `frontend/src/features/newsletters/NewsletterEditorPage.tsx:148-154`

### What is wrong

`delivery_topic` exists in the model and is written by create/update, but it is omitted from response schemas. It is also not used in actual send/unsubscribe logic.

### Confirmed observed behavior

In the disposable analysis copy:

- create response did not include `delivery_topic`
- list response did not include `delivery_topic`
- editing from list reset the stored value to `default-topic`

### Why it matters

Topic-scoped unsubscribe is one of the main pieces of newsletter compliance and audience precision. Right now it is mostly metadata with no operational authority.

### Recommended fix

1. Add `delivery_topic` to all appropriate response models.
2. Decide whether this is:
   - an internal local topic identifier, or
   - a mirror of Resend Topics.
3. Make unsubscribe semantics explicit:
   - unsubscribe from one newsletter/topic only
   - or unsubscribe globally across a logical topic family
4. Include topic metadata in run snapshots.
5. If integrating with Resend Topics, create/sync provider topics and use them deliberately.

### Acceptance criteria

- `delivery_topic` round-trips through create, list, get, update, run detail
- editing a newsletter preserves the stored topic
- unsubscribe behavior clearly maps to topic scope

---

## P0-8. Newsletter deletion destroys run history

**Severity:** P0  
**Area:** Auditability / history retention  
**Files:**
- `backend/app/models.py:72-126`
- `backend/app/api/newsletters.py:543-557`

### What is wrong

`Newsletter.runs` is configured with `cascade="all, delete-orphan"`. Deleting a newsletter removes:

- the newsletter
- all runs
- all run events

### Why it matters

That conflicts with the stated operational goal of auditability. Historical sends should survive newsletter deletion, or at minimum there must be a conscious retention strategy.

### Recommended fix

Prefer one of these:

#### Preferred
- soft-delete newsletters (`deleted_at`)
- keep runs forever unless explicitly purged

#### Alternative
- allow hard delete of newsletter definition
- keep runs with nullable `newsletter_id`
- store newsletter name/slug/topic snapshots on the run

### Acceptance criteria

- deleting a newsletter does not delete run history by default
- deleted newsletters remain identifiable in run history
- operator can still inspect old run snapshots after newsletter deletion

---

## P0-9. Current suppression/unsubscribe workflow is incomplete for real production use

**Severity:** P0  
**Area:** Compliance / deliverability / provider integration  
**Files:**
- `backend/app/api/public.py:12-30`
- `backend/app/email_delivery.py:43-213`
- `backend/app/api/runs.py:76-108`

### What is wrong

The current suppression model only supports manual local unsubscribe by token. Missing pieces:

- provider webhooks for bounce/complaint events
- signature verification for webhook ingestion
- local suppression updates from provider events
- one-click unsubscribe headers
- unsubscribe footer link in message content
- durable webhook event storage/idempotency

### Why it matters

A production newsletter system cannot rely on manual unsubscribe alone. Bounces and complaints must feed suppression automatically.

### Recommended fix

Implement a provider event pipeline:

1. add webhook endpoint
2. verify signature using raw request body
3. store every webhook event idempotently
4. map `delivered`, `bounced`, `complained`, `failed`, `suppressed`, etc. into local run events and recipient suppression state
5. append reconciliation events only once per provider event

Also add one-click unsubscribe support:

- `List-Unsubscribe`
- `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
- HTTPS unsubscribe endpoint
- visible unsubscribe footer link in body

### External references

- Gmail sender guidelines require easy unsubscribe, and for bulk senders require one-click unsubscribe via headers for marketing/subscribed mail. Body-only links or `mailto` alone do not satisfy the one-click requirement.  
  Google: `https://support.google.com/a/answer/81126?hl=en`  
  Google FAQ: `https://support.google.com/a/answer/14229414?hl=en`
- Resend supports custom headers, unsubscribe headers, webhooks, webhook signature verification, topics, and idempotency keys.  
  Resend custom headers: `https://resend.com/docs/dashboard/emails/custom-headers`  
  Resend unsubscribe for transactional mail: `https://resend.com/docs/dashboard/emails/add-unsubscribe-to-transactional-emails`  
  Resend webhooks: `https://resend.com/docs/webhooks/introduction`  
  Resend signature verification: `https://resend.com/docs/webhooks/verify-webhooks-requests`

### Acceptance criteria

- one-click unsubscribe headers are present on production sends
- public unsubscribe endpoint supports the URL flow used in headers
- webhook events are verified, stored, and deduplicated
- bounced/complained recipients are automatically suppressed for future sends

---

## P0-10. Single-user bootstrap is not actually enforced at the database level

**Severity:** P0  
**Area:** Auth / security model  
**Files:**
- `backend/app/auth.py:14-19`
- `backend/app/api/auth.py:39-62`
- `backend/app/models.py:31-37`

### What is wrong

The app intends to be single-user, but that rule is enforced only by an application-level count check.

There is **no database-level guarantee** that only one operator can exist.

That means concurrent bootstrap requests can race:

- both see user count = 0
- both insert different users
- result: multiple operators in a single-user system

There is also no setup secret, local-only restriction, or installation token protecting first bootstrap if the app is exposed before initial setup.

### Why it matters

This is a structural security mismatch: the code claims single-user, but the DB model does not enforce it.

### Recommended fix

Choose a real single-user control strategy.

#### Preferred
Use a dedicated singleton settings table:

- `system_settings(id=1, initialized, operator_user_id, bootstrap_disabled_at)`
- bootstrap transaction claims initialization atomically

#### Minimum safe fix

- require a one-time bootstrap secret from environment
- refuse bootstrap when secret is absent in non-development
- optionally restrict bootstrap to localhost until initialized

### Acceptance criteria

- only one operator can ever be created, even under concurrent bootstrap requests
- bootstrap requires deliberate installation control in production
- second bootstrap cannot succeed under race conditions

---

# P1 — High-priority correctness and reliability gaps

## P1-1. Server accepts invalid data almost everywhere

**Severity:** P1  
**Area:** Validation  
**Files:**
- `backend/app/schemas.py:27-200`
- `backend/app/api/newsletters.py:261-557`

### What is wrong

Schemas use plain strings instead of constrained types or enums for:

- email addresses
- password lengths
- newsletter status
- provider name
- template key
- timezone
- cron value
- recipient entries

### Confirmed observed behavior

In the disposable analysis copy, the server accepted a create payload containing:

- `status="banana"`
- `provider_name="typo-provider"`
- `template_key="not-a-template"`
- `timezone="NoSuch/Zone"`
- recipient `"not-an-email"`

It returned `201 Created` when scheduling was off.

### Why it matters

Garbage accepted at the API layer becomes corruption in the database and weird behavior later.

### Recommended fix

Use Pydantic validation deliberately:

- `EmailStr` for emails
- enum for newsletter status
- enum for supported template keys
- enum or allowlist for supported providers
- timezone validator using `zoneinfo`
- cron validator with explicit parse test
- min password length and maybe max length

Also validate semantic combinations:

- schedule requires active status and valid cron
- manual send requires at least one active recipient
- template key must exist

### Acceptance criteria

- invalid email/provider/template/status/timezone returns `422`
- invalid recipient import reports which entries failed
- tests cover representative invalid payloads

---

## P1-2. Send result semantics are wrong for zero-recipient and all-failed cases

**Severity:** P1  
**Area:** Delivery results  
**Files:**
- `backend/app/email_delivery.py:96-178`

### What is wrong

Current logic:

```python
overall_status = "sent" if all(item.status == "sent" for item in outcomes) else "partial"
```

This is incorrect because:

- `all([])` is `True`, so zero-recipient sends become `sent`
- if **every** recipient fails, overall status becomes `partial`, not `failed`
- message text says “attempted for all active recipients” even when there were none

### Confirmed observed behavior

Direct function testing in the disposable analysis copy showed:

- empty recipient list with configured Resend path => overall status `sent`
- all-recipient failure => overall status `partial`

### Recommended fix

Use explicit outcome rules:

- no recipients => `no_recipients` or request validation error
- all sent => `sent`
- some sent / some failed => `partial`
- none sent / all failed => `failed`

### Acceptance criteria

- overall run status matches recipient outcomes
- zero-recipient send is never reported as `sent`
- dashboard filters include `failed` if used

---

## P1-3. Run detail mixes immutable snapshot with mutable current newsletter state

**Severity:** P1  
**Area:** Run history correctness  
**Files:**
- `backend/app/api/runs.py:60-73`
- `backend/app/models.py:100-126`

### What is wrong

Run detail currently returns:

- `run` => partial snapshot data
- `newsletter` => `run.newsletter` (the **current** newsletter row)

If the newsletter is edited after a send, run detail shows current newsletter metadata next to old run snapshot data.

### Confirmed observed behavior

In the disposable analysis copy:

- run snapshot subject remained `Subj 1`
- after editing the newsletter, `GET /api/runs/{id}` showed the newsletter’s **new** name/template in the run detail response

### Why it matters

This makes run detail historically misleading.

### Recommended fix

Either:

- stop returning mutable current newsletter state in run detail, or
- label it clearly as current state and add a separate immutable `newsletter_snapshot`

Suggested snapshot additions on run:

- `newsletter_name`
- `newsletter_slug`
- `delivery_topic`
- `status_at_run_time`
- `template_key_used`
- `provider_name_used`
- `model_name_used`

### Acceptance criteria

- run detail can be understood without consulting current newsletter state
- editing a newsletter later does not rewrite historical meaning of old runs

---

## P1-4. Recipient suppression durability is weak; edit-by-replacement can erase suppressed addresses

**Severity:** P1  
**Area:** Audience model / compliance  
**Files:**
- `backend/app/api/newsletters.py:84-112`
- `backend/app/models.py:78-98`

### What is wrong

Recipients are managed by replacing the entire relationship list from imported text.

That means suppressed or unsubscribed recipients can disappear entirely if omitted from a later edit. Once deleted, they can be re-added as fresh active recipients with a new token.

There is also no database-level uniqueness constraint on `(newsletter_id, email)`.

### Why it matters

Suppression should be durable and difficult to erase accidentally.

### Recommended fix

Refactor recipient handling:

- add unique constraint on `(newsletter_id, email)`
- do not use delete-orphan semantics for compliance history
- use soft states instead:
  - `subscribed`
  - `unsubscribed`
  - `suppressed_bounce`
  - `suppressed_complaint`
  - `removed_by_operator`
- import should upsert, not replace the table wholesale

### Acceptance criteria

- re-importing a recipient does not bypass suppression history
- unsubscribed/suppressed recipients remain represented even after list edits
- duplicate email rows per newsletter are impossible

---

## P1-5. AI generation is brittle because it relies on free-form parsing and silent fallback

**Severity:** P1  
**Area:** AI draft reliability  
**Files:**
- `backend/app/ai_generation.py:24-125`

### What is wrong

Generation depends on free-form model output matching an exact text layout:

- `SUBJECT:`
- `PREHEADER:`
- `BODY:`

Any provider drift or formatting variance can degrade parsing silently.

Unknown or mistyped provider names also silently route to local fallback if credentials are absent.

### Why it matters

For a “simple but precise and reliable” tool, silent fallback on provider typo or malformed AI output is too forgiving.

### Recommended fix

- validate provider name against supported set
- switch to structured JSON output where possible
- use low temperature and explicit output schema
- add timeout/retry policy and explicit “live provider unavailable” statuses
- optionally make fallback generation opt-in in production, not silent default

### Acceptance criteria

- generation either returns structured content or explicit failure/fallback state
- provider typos are rejected, not silently downgraded
- malformed AI output cannot produce partial garbage silently

---

## P1-6. Date range filtering is wrong for `date_to`

**Severity:** P1  
**Area:** Dashboard filtering  
**Files:**
- `backend/app/api/runs.py:33-57`
- `frontend/src/features/dashboard/RunDashboardPage.tsx:53-70, 137-145`

### What is wrong

The frontend sends `YYYY-MM-DD` date strings. FastAPI/Pydantic parses those to midnight datetimes.

Then the backend uses:

- `created_at >= date_from`
- `created_at <= date_to`

So `date_to=2026-04-10` becomes `2026-04-10T00:00:00`, which excludes runs from most of that day.

### Confirmed observed behavior

In the disposable analysis copy:

- a run created on a day was returned by `date_from=<same day>`
- the same run was **not** returned by `date_to=<same day>`

### Recommended fix

Use date semantics, not naive datetime semantics:

- parse `date_from` and `date_to` as `date`, not `datetime`
- convert internally to:
  - `date_from` => start of day inclusive
  - `date_to` => next day start exclusive

### Acceptance criteria

- selecting the same date in `date_to` includes that day’s runs
- tests cover same-day filters and timezone edges

---

## P1-7. Scheduler architecture is only safe if exactly one scheduler process is running

**Severity:** P1  
**Area:** Scheduling / deployment architecture  
**Files:**
- `backend/app/scheduler.py:19-98`
- `backend/app/main.py:17-22`

### What is wrong

The app uses in-process APScheduler with a persistent SQLAlchemy job store.

This is acceptable only if there is exactly one scheduler process. If multiple app processes or multiple containers point at the same DB, duplicate or missed execution can occur.

### Why it matters

The codebase currently has no explicit runtime guard preventing a multi-worker deployment.

### External reference

APScheduler documentation explicitly warns that persistent job stores must not be shared between schedulers/processes.  
`https://apscheduler.readthedocs.io/en/stable/faq.html`  
`https://apscheduler.readthedocs.io/en/3.x/userguide.html`

### Recommended fix

You have two viable choices:

#### Keep it simple (recommended for this project)
- document and enforce **single container, single process, single scheduler**
- set the runtime command to one worker only
- add explicit startup warning if worker count is greater than one

#### Or separate the scheduler role
- dedicated scheduler mode / process
- web app process without scheduler

### Acceptance criteria

- deployment documentation explicitly states single-scheduler constraint
- production compose/systemd config runs only one scheduler process
- no duplicate scheduled execution under restart/redeploy scenarios

---

## P1-8. Production delivery misconfiguration can silently degrade into local-preview simulation

**Severity:** P1  
**Area:** Delivery safety  
**Files:**
- `backend/app/email_delivery.py:43-56, 96-119`
- `backend/app/config.py:12-39`

### What is wrong

If Resend API key/from address are missing, the app returns local-preview fallback/simulated results instead of hard-failing.

This is convenient in development, but dangerous in production because a transport outage/misconfiguration can look superficially successful.

### Recommended fix

Differentiate behavior by environment:

- development: preview fallback allowed
- production: live send requires verified send configuration and should hard-fail loudly if absent

Also expose configuration status in the UI or health endpoint.

### Acceptance criteria

- production sends fail clearly when Resend config is missing
- development can still use preview-only fallback if desired
- operator UI shows transport readiness status

---

## P1-9. No database migration system; schema evolution is fragile

**Severity:** P1  
**Area:** Persistence / deployability  
**Files:**
- `backend/app/database.py:38-40`

### What is wrong

The project uses `Base.metadata.create_all()` directly and has no Alembic migration workflow.

### Why it matters

The backlog above requires schema changes. Without migrations, any real deployment upgrade becomes risky.

### External reference

Alembic is the standard SQLAlchemy migration tool and supports versioned schema changes and autogeneration.  
`https://alembic.sqlalchemy.org/en/latest/tutorial.html`

### Recommended fix

- initialize Alembic
- create baseline migration from current schema
- switch startup from `create_all()` to `alembic upgrade head`
- add migration runbook for SQLite upgrades and backups

### Acceptance criteria

- schema changes are represented as reviewed migrations
- startup does not mutate schema implicitly
- upgrade path is documented and repeatable

---

## P1-10. Docker/build chain is not reproducible or hardened enough

**Severity:** P1  
**Area:** Packaging / deployability  
**Files:**
- `Dockerfile:1-22`
- `frontend/package-lock.json`
- `backend/pyproject.toml`

### What is wrong

Current issues:

- frontend build uses `npm install` instead of `npm ci`
- Dockerfile does not copy `package-lock.json` into the build stage
- backend has no lockfile/constraints strategy
- container runs as root
- no explicit volume guidance for persistent data
- no healthcheck

### Recommended fix

- copy `package-lock.json`
- use `npm ci`
- add Python constraints or locked dependency export
- create non-root user in runtime image
- document `PULSE_NEWS_DATA_DIR` volume mount
- add container healthcheck against `/api/health`

### Acceptance criteria

- repeated builds are deterministic
- runtime does not run as root
- deployment docs show persistent data volume usage clearly

---

# P2 — Important improvements and polish

## P2-1. Password storage and secret handling should be hardened

**Severity:** P2  
**Area:** Security  
**Files:**
- `backend/app/security.py:17-45`
- `backend/app/config.py:15-18`
- `backend/app/api/auth.py:88-104`
- `backend/app/auth.py:32-38`

### What is wrong

- secret key still has a dangerous default value
- password hashing is hand-rolled scrypt storage
- verify path does not guard malformed hash formats robustly
- password change does not rotate/invalidate existing sessions

### External reference

OWASP currently recommends Argon2id first, and stronger scrypt parameters than the current ones if Argon2id is unavailable.  
`https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html`

### Recommended fix

- fail startup in production if secret key is default/weak
- switch to Argon2id (or stronger scrypt strategy if staying stdlib-only)
- add hash versioning and malformed-hash handling
- rotate session after login/password change
- optionally add session version so password changes invalidate all active sessions

### Acceptance criteria

- production cannot start with default secret
- password hashes are versioned and verifiable safely
- password change invalidates old sessions

---

## P2-2. Auth operational hardening is missing

**Severity:** P2  
**Area:** Security / ops  
**Files:**
- `backend/app/api/auth.py:29-104`

### What is wrong

There is no:

- login throttling
- auth audit trail
- suspicious access logging
- brute-force protection

### Recommended fix

- add simple rate limit or backoff on login attempts
- write audit events for bootstrap, login success/failure, logout, password change
- expose recent auth events in operator UI later if needed

---

## P2-3. Test suite is too happy-path-focused

**Severity:** P2  
**Area:** QA  
**Files:**
- `backend/tests/*.py`
- `backend/pyproject.toml:31-33`

### What is wrong

The current tests cover basic CRUD/generate/send flows, but they do not cover the defects above.

Also, pytest configuration is wrong for the directory it lives in:

- `testpaths = ["backend/tests"]`
- when running from `backend/`, pytest warns that no files were found in `testpaths`

### Recommended fix

Change pytest config to match actual execution context, likely:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Then add regression tests for:

- delete route startup/import
- list-edit recipient/topic preservation
- invalid cron/timezone returns `422`
- no-cron resume blocked
- archived/paused send blocked
- zero-recipient send blocked
- all-failed send => `failed`
- invalid enums/emails rejected
- run snapshot immutability
- newsletter delete preserves runs
- webhook signature verification and suppression updates
- same-day `date_to` filtering

### Acceptance criteria

- the bugs in this document each have at least one regression test where practical
- CI fails on contract drift

---

## P2-4. Run dashboard and UI error handling need improvement

**Severity:** P2  
**Area:** Frontend UX  
**Files:**
- `frontend/src/features/dashboard/RunDashboardPage.tsx:59-89`
- `frontend/src/lib/api.ts:84-205`
- `frontend/src/features/newsletters/newsletter-types.ts:21-26`

### What is wrong

- run dashboard async calls have no error handling
- selected run loading is optimistic and can fail noisily
- recipient suppression metadata returned by backend detail is not typed/displayed in the frontend
- generation result type omits the returned `run`
- run/newsletter type boundaries are blurred

### Recommended fix

- add loading/error states for run list, run detail, reconcile
- split summary/detail types cleanly
- include suppression state in recipient UI
- expose generation run result if useful operationally

---

## P2-5. API shape should stop returning JSON-as-string blobs

**Severity:** P2  
**Area:** API design / maintainability  
**Files:**
- `backend/app/models.py:118-121`
- `backend/app/schemas.py:132-200`
- `backend/app/api/runs.py:64-108`

### What is wrong

Several fields are stored and exposed as JSON strings:

- `snapshot_recipient_emails`
- `delivery_outcomes`

That forces extra parsing and weakens schema guarantees.

### Recommended fix

Prefer one of these:

- normalize recipients/outcomes/events into relational tables
- or use typed JSON columns where supported and expose typed arrays in API schemas

For a simple v1, relational outcomes + events is the cleanest path.

---

## P2-6. Sequential per-recipient sending is simple but inefficient

**Severity:** P2  
**Area:** Performance / provider usage  
**Files:**
- `backend/app/email_delivery.py:121-178`

### What is wrong

The app sends one HTTP request per recipient.

That is acceptable at tiny volume, but it is inefficient and makes long-running sends more fragile.

### External reference

Resend provides batch send support for up to 100 emails per API call and supports idempotency keys there as well.  
`https://resend.com/docs/api-reference/emails/send-batch-emails`  
`https://resend.com/docs/dashboard/emails/batch-sending`

### Recommended fix

- keep per-recipient personalization if needed
- otherwise use batch send when payload is uniform
- add retry/backoff for transient provider errors

---

## P2-7. Delivery event reconciliation is additive but not deduplicated

**Severity:** P2  
**Area:** Run event model  
**Files:**
- `backend/app/api/runs.py:76-108`

### What is wrong

Every reconcile click appends new events regardless of whether the provider status changed.

### Recommended fix

- track last known provider event per provider ID
- append only on state change
- store raw provider event payloads separately if webhooks are added

---

## P2-8. UI copy and operator experience are stale in places

**Severity:** P2  
**Area:** Frontend polish  
**Files:**
- `frontend/src/App.tsx:223`
- `frontend/src/features/newsletters/NewsletterListPage.tsx:41-44`
- `README.md:1`

### What is wrong

- app title still says `Foundation and Secure Control Plane`
- empty-state copy still refers to later phases as if features are not implemented
- README is effectively empty

### Recommended fix

- refresh all phase-era copy to current product language
- write a real README with setup, env vars, running, sending, backups, restore, and upgrade steps

---

# Deliverability and compliance work that should be added explicitly

This is important enough to break out separately.

## Required operational deliverability checklist

Before using this as a real newsletter sender, add a checklist and corresponding diagnostics:

1. verified sending domain in Resend
2. SPF passing
3. DKIM passing
4. DMARC record published
5. `List-Unsubscribe` header present
6. `List-Unsubscribe-Post: List-Unsubscribe=One-Click` present where required
7. visible unsubscribe link in body/footer
8. bounce/complaint webhook configured and verified
9. provider suppression state reconciled into local suppression state
10. provider configuration visible in admin UI

### External references

- Google sender requirements and one-click unsubscribe guidance:  
  `https://support.google.com/a/answer/81126?hl=en`  
  `https://support.google.com/a/answer/14229414?hl=en`
- Resend domain verification and DMARC guidance:  
  `https://resend.com/docs/dashboard/domains/introduction`  
  `https://resend.com/docs/dashboard/domains/dmarc`
- Resend suppression behavior:  
  `https://resend.com/docs/dashboard/emails/email-suppressions`

---

# Recommended implementation order

## Phase A — Stabilize correctness first

1. Fix delete-route startup/import blocker.
2. Split newsletter summary/detail contracts and fetch detail before edit.
3. Add validation layer for status/template/provider/timezone/cron/email.
4. Validate schedule before commit.
5. Block archived/paused/no-recipient sends.
6. Fix send status semantics (`sent` / `partial` / `failed` / `no_recipients`).

## Phase B — Make history durable and trustworthy

7. Create runs before sending.
8. Store real rendered snapshots, including HTML/plain-text and prompt snapshot.
9. Stop run detail from mixing old run with mutable current newsletter meaning.
10. Preserve run history on newsletter delete.

## Phase C — Finish compliance properly

11. Repair `delivery_topic` round-trip and semantics.
12. Add unsubscribe footer + one-click headers.
13. Add webhook endpoint + signature verification + provider event persistence.
14. Sync bounces/complaints/suppressions into local recipient state.

## Phase D — Harden deployment and maintenance

15. Add Alembic migrations.
16. Enforce non-default production secret.
17. Harden password storage/session invalidation.
18. Fix Docker reproducibility and non-root runtime.
19. Document single-scheduler deployment constraint or separate scheduler role.

## Phase E — Expand tests and operator tooling

20. Add regression tests for every P0/P1 defect.
21. Add audit event APIs/UI if you want true operator auditability.
22. Improve dashboard filtering, pagination, and error handling.

---

# Suggested issue backlog (copy/paste ready)

## Blockers

- [ ] Fix `DELETE /newsletters/{id}` 204 route registration/startup compatibility.
- [ ] Split newsletter list summary and detail contracts; fetch detail before edit.
- [ ] Add validation for status/provider/template/timezone/cron/recipient email.
- [ ] Prevent invalid schedule state from being committed.
- [ ] Block manual/scheduled sends for paused and archived newsletters.
- [ ] Reject zero-recipient sends explicitly.
- [ ] Fix overall send status calculation for all-failed and zero-recipient cases.

## Durability / history

- [ ] Create run row before external send.
- [ ] Add attempt key + provider idempotency support.
- [ ] Store rendered HTML/plain text/subject/preheader on run.
- [ ] Store prompt snapshot on generation/send runs.
- [ ] Stop run detail from showing mutable current newsletter as if it were historical truth.
- [ ] Preserve run history when newsletter definitions are deleted.

## Compliance / delivery

- [ ] Add `delivery_topic` to response schemas and frontend detail handling.
- [ ] Decide and implement topic unsubscribe semantics.
- [ ] Add `List-Unsubscribe` and `List-Unsubscribe-Post` headers.
- [ ] Add unsubscribe footer links to rendered emails.
- [ ] Add webhook ingestion with signature verification.
- [ ] Suppress bounced/complained recipients automatically.
- [ ] Add provider event deduplication.

## Security / auth

- [ ] Enforce real single-user bootstrap semantics.
- [ ] Require bootstrap secret or local-only bootstrap in production.
- [ ] Enforce non-default secret key in production.
- [ ] Upgrade password hashing strategy.
- [ ] Invalidate old sessions after password change.
- [ ] Add auth audit events and simple login throttling.

## Persistence / deploy

- [ ] Introduce Alembic migrations.
- [ ] Add recipient uniqueness constraint.
- [ ] Replace destructive recipient list replacement with upsert/soft-state behavior.
- [ ] Fix Dockerfile to use lockfiles and non-root runtime.
- [ ] Add deployment runbook and data backup/restore docs.

## Frontend / UX

- [ ] Add dashboard loading/error states.
- [ ] Fix type mismatches in `api.ts` and newsletter/run types.
- [ ] Surface suppression metadata in UI.
- [ ] Add confirmations for delete/archive/live send actions.
- [ ] Refresh stale product copy and README.

---

# Test plan to add immediately

## Backend tests

- [ ] app imports successfully
- [ ] delete route returns 204 with empty body
- [ ] create invalid cron returns 422 and does not persist row
- [ ] create invalid timezone returns 422
- [ ] create invalid status/provider/template/email returns 422
- [ ] resume schedule without cron fails
- [ ] archived newsletter cannot send
- [ ] paused newsletter cannot send
- [ ] zero-recipient send fails
- [ ] all-failed delivery returns `failed`
- [ ] edit-from-list equivalent payload does not wipe recipients/topic
- [ ] deleting newsletter preserves run history
- [ ] run snapshot remains immutable after newsletter edits
- [ ] webhook signature verification rejects invalid signatures
- [ ] webhook bounce/complaint suppresses recipient
- [ ] `date_to` includes the entire selected day

## Frontend tests

- [ ] edit flow fetches detail before populating editor
- [ ] saving from list-derived edit preserves recipients and topic
- [ ] dashboard displays request errors cleanly
- [ ] live-send confirmation workflow works as intended

---

# Minimal target architecture after fixes

This project does **not** need a queue system or multi-service rewrite yet.

A good near-term target is:

- FastAPI app
- React frontend bundled into the same container
- SQLite for small self-hosted installs
- APScheduler **only if** one process is guaranteed
- Alembic for schema changes
- Resend as delivery system of record
- local DB as audit/snapshot system of record
- webhook ingestion for delivery state and suppression sync

That is still simple. It is also much safer than the current state.

---

# Bottom line

The project is close enough that it should be repaired, not replaced.

The first production-worthy milestone is not “more features.” It is this:

1. stop startup/runtime breakage
2. stop silent data loss from the edit flow
3. make send attempts durable and idempotent
4. validate schedule/state before commit
5. make unsubscribe/suppression real
6. preserve trustworthy history

Once those are in place, the platform can remain intentionally small and still be precise and reliable.
