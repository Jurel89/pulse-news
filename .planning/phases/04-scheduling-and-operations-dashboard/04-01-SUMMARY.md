---
phase: 04-scheduling-and-operations-dashboard
plan: 01
subsystem: infra
tags: [scheduler, apscheduler, recurring, jobs]
requires:
  - phase: 03-ai-generation-and-manual-delivery
    provides: shared send execution path and run model
provides:
  - APScheduler service
  - Deterministic newsletter schedule jobs
  - Schedule enable/disable controls
affects: [dashboard, compliance]
tech-stack:
  added: [apscheduler]
  patterns: [deterministic-job-ids, schedule-reconciliation]
key-files:
  created: [backend/app/scheduler.py]
  modified: [backend/app/models.py, backend/app/api/newsletters.py, backend/app/main.py]
key-decisions:
  - "Keep schedule state explicit on newsletters with schedule_enabled"
  - "Use startup reconciliation and replace_existing job writes to avoid duplicate jobs"
patterns-established:
  - "Scheduled sends call the same backend execution helper as manual sends"
  - "Job IDs are newsletter-send-{id}"
requirements-completed: [SEND-02, SEND-03]
duration: 30min
completed: 2026-04-09
---

# Phase 4: Scheduling and Operations Dashboard Summary

**Recurring scheduling is now part of the app, with APScheduler-backed job reconciliation and explicit schedule controls**

## Performance

- **Duration:** 30 min
- **Started:** 2026-04-09T22:50:00+02:00
- **Completed:** 2026-04-09T23:26:40+02:00
- **Tasks:** 1
- **Files modified:** 16

## Accomplishments
- Added scheduler service and startup/shutdown integration.
- Added explicit schedule enable/disable state to newsletters.
- Kept scheduled sends on the same execution helper as manual sends.

## Task Commits

1. **Task 1: APScheduler and recurring execution controls** - `f4ab1f3` (feat)

## Decisions Made

- Deterministic job IDs plus `replace_existing` were used to prevent duplicate jobs after reconciliation.

## Deviations from Plan

None - plan executed as intended.

## User Setup Required

None.

## Next Phase Readiness

The dashboard can now observe scheduled and manual runs from the same execution model.

---
*Phase: 04-scheduling-and-operations-dashboard*
*Completed: 2026-04-09*
