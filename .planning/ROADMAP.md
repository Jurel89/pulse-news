# Roadmap: Pulse News

## Overview

Pulse News moves from a secure single-user control plane to a fully operational newsletter console in five phases. The roadmap starts by making the product safe and structurally sound, then adds draft workflow and template previewing, then manual AI-assisted sending through Resend, then recurring scheduling with operational visibility, and finally compliance and delivery hardening that make recurring production use trustworthy.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation and Secure Control Plane** - Build the authenticated app shell and core newsletter management domain.
- [x] **Phase 2: Draft Workflow and Template System** - Add recipient management, themed templates, previews, and test sends.
- [x] **Phase 3: AI Generation and Manual Delivery** - Add provider abstraction, draft generation, manual runs, and Resend-backed sending.
- [x] **Phase 4: Scheduling and Operations Dashboard** - Add recurring schedules, restart-safe jobs, and run history dashboards.
- [x] **Phase 5: Compliance and Delivery Hardening** - Add unsubscribe/topic enforcement, delivery reconciliation, and operational polish.

## Phase Details

### Phase 1: Foundation and Secure Control Plane
**Goal**: Deliver a protected single-user application shell with durable core data models for newsletters and account management.
**Depends on**: Nothing (first phase)
**Requirements**: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, NEWS-01, NEWS-02, NEWS-03, NEWS-04]
**Success Criteria** (what must be TRUE):
  1. Operator can bootstrap a local admin account and authenticate into the responsive UI.
  2. Operator can create, edit, pause, archive, and intentionally delete newsletter definitions.
  3. Protected routes stay inaccessible without an authenticated session.
  4. Newsletter configuration data persists across app restarts.
**Plans**: 3 plans

Plans:
- [ ] 01-01: Create backend/frontend app shells, shared config, and container baseline
- [ ] 01-02: Implement single-user authentication and secure session handling
- [ ] 01-03: Implement newsletter domain models and CRUD UI/API

### Phase 2: Draft Workflow and Template System
**Goal**: Let the operator prepare newsletters safely through recipients, themed templates, previews, and test sends before live delivery.
**Depends on**: Phase 1
**Requirements**: [AUD-01, TPL-01, TPL-02, TPL-03]
**Success Criteria** (what must be TRUE):
  1. Operator can manage newsletter recipients and associate them with a newsletter.
  2. Operator can select a reusable template family and preview HTML and plain text output.
  3. Operator can send a test version of a draft to a designated address.
  4. Template and recipient settings persist and are editable later.
**Plans**: 3 plans

Plans:
- [ ] 02-01: Implement recipient data model, import/manual management, and newsletter association
- [ ] 02-02: Implement React Email template families, theme configuration, and render pipeline
- [ ] 02-03: Implement preview and test-send workflows in the UI and backend

### Phase 3: AI Generation and Manual Delivery
**Goal**: Add multi-provider draft generation, immutable run snapshots, and manual newsletter delivery through Resend.
**Depends on**: Phase 2
**Requirements**: [GEN-01, GEN-02, GEN-03, GEN-04, SEND-01, SEND-04]
**Success Criteria** (what must be TRUE):
  1. Operator can generate a draft using the configured prompt and provider/model settings.
  2. Operator can manually run a newsletter and dispatch it through Resend.
  3. Every run stores immutable prompt, provider, model, content, and delivery metadata.
  4. Provider and delivery failures surface clearly in the UI and logs.
**Plans**: 4 plans

Plans:
- [ ] 03-01: Implement provider abstraction and LiteLLM-backed generation service
- [ ] 03-02: Implement run orchestration and immutable snapshot persistence
- [ ] 03-03: Implement Resend delivery service and manual-send UI/API
- [ ] 03-04: Normalize generation and send errors for operator review

### Phase 4: Scheduling and Operations Dashboard
**Goal**: Make the product operationally useful for recurring sends with restart-safe scheduling and clear run visibility.
**Depends on**: Phase 3
**Requirements**: [AUD-04, SEND-02, SEND-03, DASH-01, DASH-02, DASH-03]
**Success Criteria** (what must be TRUE):
  1. Operator can create, pause, and resume recurring schedules from the UI.
  2. Scheduled jobs survive container restarts without duplicate future runs.
  3. Operator can inspect run history and detailed run records from the dashboard.
  4. Dashboard filters let the operator narrow history by newsletter, status, and date range.
**Plans**: 3 plans

Plans:
- [ ] 04-01: Implement APScheduler-backed persistent scheduling and job reconciliation
- [ ] 04-02: Build runs dashboard, list filters, and detail views
- [ ] 04-03: Unify manual and scheduled execution paths under the same run lifecycle

### Phase 5: Compliance and Delivery Hardening
**Goal**: Enforce recipient compliance and improve delivery-state trust for ongoing production use.
**Depends on**: Phase 4
**Requirements**: [AUD-02, AUD-03, DASH-04]
**Success Criteria** (what must be TRUE):
  1. Each newsletter is associated with an unsubscribe/topic scope or equivalent delivery rule.
  2. Suppressed or unsubscribed recipients are excluded automatically from live sends.
  3. Operator can review delivery-state reconciliation updates after sending.
  4. Delivery-related operational edge cases are visible in the dashboard and logs.
**Plans**: 2 plans

Plans:
- [ ] 05-01: Implement topic/unsubscribe mapping and recipient suppression enforcement
- [ ] 05-02: Implement delivery reconciliation, event updates, and operational hardening

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and Secure Control Plane | 3/3 | Complete | 2026-04-09 |
| 2. Draft Workflow and Template System | 3/3 | Complete | 2026-04-09 |
| 3. AI Generation and Manual Delivery | 4/4 | Complete | 2026-04-09 |
| 4. Scheduling and Operations Dashboard | 3/3 | Complete | 2026-04-09 |
| 5. Compliance and Delivery Hardening | 2/2 | Complete | 2026-04-09 |
