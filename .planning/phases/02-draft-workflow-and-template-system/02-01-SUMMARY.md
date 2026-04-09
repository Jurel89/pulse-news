---
phase: 02-draft-workflow-and-template-system
plan: 01
subsystem: database
tags: [recipients, drafts, crud, react, fastapi]
requires:
  - phase: 01-foundation-and-secure-control-plane
    provides: authenticated newsletter CRUD shell
provides:
  - Newsletter draft subject/preheader/body fields
  - Newsletter-scoped recipients with import parsing
  - Editor support for draft and recipient preparation
affects: [templates, preview, test-send, compliance]
tech-stack:
  added: []
  patterns: [newsletter-scoped-recipients, backend-recipient-normalization]
key-files:
  created: []
  modified: [backend/app/models.py, backend/app/api/newsletters.py, frontend/src/features/newsletters/NewsletterEditorPage.tsx]
key-decisions:
  - "Store recipients under each newsletter for v1 rather than building shared segments"
  - "Persist draft content separately from prompts so previews and sends use actual editorial material"
patterns-established:
  - "Recipient import text is normalized server-side into concrete recipient rows"
  - "Newsletter detail responses can expose richer editor-facing fields than list responses"
requirements-completed: [AUD-01]
duration: 24min
completed: 2026-04-09
---

# Phase 2: Draft Workflow and Template System Summary

**Newsletter definitions now carry real draft content and newsletter-scoped recipients for later preview and send flows**

## Performance

- **Duration:** 24 min
- **Started:** 2026-04-09T19:40:00+02:00
- **Completed:** 2026-04-09T20:04:00+02:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added draft subject, preheader, and body fields to newsletter persistence.
- Added newsletter-scoped recipients with backend normalization of manual/CSV-style import text.
- Extended the newsletter editor so draft and recipient preparation happen in one place.

## Task Commits

Each task was committed atomically:

1. **Task 1-2: Recipient model/API and editor support** - `37d3a0a` (feat)

**Plan metadata:** `37d3a0a` (code and plan completion captured together for recipient and draft preparation)

## Files Created/Modified
- `backend/app/models.py` - newsletter draft fields and recipient table
- `backend/app/api/newsletters.py` - recipient import normalization and richer newsletter detail serialization
- `backend/app/schemas.py` - draft and recipient API shapes
- `backend/tests/test_newsletters.py` - newsletter draft/recipient coverage
- `frontend/src/features/newsletters/NewsletterEditorPage.tsx` - editor support for draft content and recipients

## Decisions Made

- Recipient parsing happens on the backend so the UI stays thin and later clients can reuse the same import logic.
- Draft content is stored on the newsletter definition itself at this stage, which is enough for preview/test-send without introducing a separate drafts subsystem yet.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The newsletter detail contract needed to grow beyond the list-view shape once recipients and draft content were added. The API now keeps the detail serializer explicit rather than overloading the summary model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Template rendering and preview flows now have real content and recipients to work with.
Phase 2 Plan 02 can build the preview layer on top of concrete newsletter draft data.

---
*Phase: 02-draft-workflow-and-template-system*
*Completed: 2026-04-09*
