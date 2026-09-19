# lane.statusfresh -- the live status is fresh and looks eleven hours stale

Issue: none (harness defect, dispatched directly). Files: `docs/testing/jobs/status.sh`,
`docs/testing/jobs/selftest.d/62-status-freshness.sh`, this file.

## The defect, restated as a rendering fact

GitHub renders a comment's `created_at` next to the author's name and leaves the
comment where it was posted in the timeline. An in-place `PATCH` moves neither.
So #107 read `02:28Z` while holding a body written at `13:32Z`, and the body's
own `_Rewritten ... by status.sh_` line -- correct, and eleven minutes old -- sat
below the fold of what the page shows first, contradicting the timestamp the UI
puts above it. Two states that must be told apart, a jammed fleet and a running
one, rendered identically.

## What was measured before choosing

(filled in as the lane runs -- see "Measurements" below)

## Measurements

(pending)

## What the next lane should not repeat

(pending)
