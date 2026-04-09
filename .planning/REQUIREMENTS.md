# Requirements: Pulse News

**Defined:** 2026-04-09
**Core Value:** One operator can reliably create and send multiple AI-assisted newsletters from a single, self-hosted control panel without juggling separate tools for content generation, scheduling, sending, and auditability.

## v1 Requirements

### Authentication

- [ ] **AUTH-01**: Operator can bootstrap the first local admin account securely during initial setup.
- [ ] **AUTH-02**: Operator can log in and log out with email and password.
- [ ] **AUTH-03**: Operator session persists across browser refresh and protects all admin routes.
- [ ] **AUTH-04**: Operator can change their password without direct database edits.

### Newsletter Management

- [ ] **NEWS-01**: Operator can create a newsletter with a name, description, and unique identifier.
- [ ] **NEWS-02**: Operator can edit newsletter prompt, provider/model settings, template selection, recipients, and schedule configuration.
- [ ] **NEWS-03**: Operator can pause or archive a newsletter without deleting its historical runs.
- [ ] **NEWS-04**: Operator can delete a newsletter definition intentionally while preserving an audit record of the action.

### Audience and Compliance

- [ ] **AUD-01**: Operator can manage recipients for a newsletter through manual entry or import.
- [ ] **AUD-02**: Operator can associate each newsletter with a distinct delivery topic or equivalent unsubscribe scope.
- [ ] **AUD-03**: Unsubscribed or suppressed recipients are excluded from future sends automatically.
- [ ] **AUD-04**: Operator can review the recipient snapshot used for a given run after it completes.

### Templates and Draft Workflow

- [ ] **TPL-01**: Operator can choose from reusable email template families with distinct aesthetics.
- [ ] **TPL-02**: Operator can preview the rendered HTML and plain-text output for a newsletter draft before sending.
- [ ] **TPL-03**: Operator can send a test version of a newsletter draft to a specified test address before a production send.

### AI Generation and Providers

- [ ] **GEN-01**: Operator can generate a newsletter draft using the configured prompt and selected provider/model.
- [ ] **GEN-02**: Provider/model selection is configured through a common abstraction that can support multiple vendors.
- [ ] **GEN-03**: Generation failures surface a normalized error message in the UI and are stored in the run log.
- [ ] **GEN-04**: The exact prompt, provider, model, and generated content used for a run are stored as an immutable snapshot.

### Delivery and Scheduling

- [ ] **SEND-01**: Operator can run a newsletter manually on demand from the UI.
- [ ] **SEND-02**: Operator can define a recurring schedule for a newsletter and pause or resume that schedule.
- [ ] **SEND-03**: Scheduled jobs persist across application restarts without duplicating future sends.
- [ ] **SEND-04**: Newsletter delivery is executed through Resend and the application stores the outbound send result for each run.

### Dashboard and Auditability

- [ ] **DASH-01**: Operator can view a dashboard of newsletter runs with status, timestamps, newsletter identity, and provider/model metadata.
- [ ] **DASH-02**: Operator can inspect a run detail page with content snapshot, recipients, generation logs, and delivery results.
- [ ] **DASH-03**: Operator can filter run history by newsletter, status, and date range.
- [ ] **DASH-04**: Operator can review delivery-state updates or reconciliation events for previously sent newsletters.

## v2 Requirements

### Collaboration and Growth

- **V2-01**: Multiple operators can access the app with role-based permissions.
- **V2-02**: Public subscription pages and subscriber self-management are built into the product.
- **V2-03**: A/B testing or campaign experimentation is available per newsletter.
- **V2-04**: Engagement analytics beyond send/delivery status are tracked in-product.

### Advanced Editorial Automation

- **V2-05**: Operator can apply AI rewrite actions to specific sections of a draft.
- **V2-06**: Provider fallback chains and policy-based routing are configurable per newsletter.
- **V2-07**: Incoming replies or inbound events can trigger follow-up workflows.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Public marketing site or newsletter CMS | Not part of the operator-only v1 scope |
| Multi-user collaboration | User requested proper single-user authentication, not team workflows |
| Drag-and-drop email builder | Adds major complexity without improving the core AI-assisted template approach |
| Multi-container worker/queue architecture | Conflicts with the explicit single-container deployment constraint |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Complete |
| AUTH-02 | Phase 1 | Complete |
| AUTH-03 | Phase 1 | Complete |
| AUTH-04 | Phase 1 | Complete |
| NEWS-01 | Phase 1 | Complete |
| NEWS-02 | Phase 1 | Complete |
| NEWS-03 | Phase 1 | Complete |
| NEWS-04 | Phase 1 | Complete |
| AUD-01 | Phase 2 | Complete |
| AUD-02 | Phase 5 | Pending |
| AUD-03 | Phase 5 | Pending |
| AUD-04 | Phase 4 | Pending |
| TPL-01 | Phase 2 | Complete |
| TPL-02 | Phase 2 | Complete |
| TPL-03 | Phase 2 | Complete |
| GEN-01 | Phase 3 | Complete |
| GEN-02 | Phase 3 | Complete |
| GEN-03 | Phase 3 | Complete |
| GEN-04 | Phase 3 | Complete |
| SEND-01 | Phase 3 | Complete |
| SEND-02 | Phase 4 | Pending |
| SEND-03 | Phase 4 | Pending |
| SEND-04 | Phase 3 | Complete |
| DASH-01 | Phase 4 | Pending |
| DASH-02 | Phase 4 | Pending |
| DASH-03 | Phase 4 | Pending |
| DASH-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-09 after initial definition*
