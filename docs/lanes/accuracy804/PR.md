# accuracy804: why RalliSport's rival cars are drawn on alternate frames (#804)

State: draft

Lane: accuracy804          Issue: #804
Base: master @ 5e4196fefd
Files: docs/lanes/accuracy804/NOTES.md, docs/lanes/accuracy804/OUTBOX.md, docs/lanes/accuracy804/PR.md, docs/lanes/accuracy804/WAITING, docs/lanes/accuracy804/alt_draws.py, docs/lanes/accuracy804/rallisport-804.route, docs/lanes/accuracy804/reports-804.diff
Prediction: none: attribution capture (frame dump), not an A/B arm
Needs device: yes (one Nova soak, queued)    Needs NDK: no

**Candidate cause, found in code.** After a deferred finish (flip, stall), `pgraph_vk_process_pending_reports_internal`
(vk/reports.c) reads the occlusion query pool before the GPU has run the command buffer that reset and filled it.
On Turnip the slot still reads as available with the previous command buffer's count, so `WAIT_BIT` returns the
old count at once. A game that draws a car body only if the last frame's visibility test passed then gets the test
from two frames back. That locks the body into an on/off pattern on alternate frames, with the shadow drawn every
frame, which is what flicker801 captured. Upstream xemu waits on the fence before this read; hakuX's deferred
fences dropped the wait.

**Open:** does RalliSport gate the body on a visibility test? Nova capture `1791136124-lane.accuracy804-3752333`
(frame dump of the rival pass + perflog `qry` counts) answers it; NOTES section 6 has the decision table.

**Fix (not applied):** `reports-804.diff` waits the submitted frames' fences when queries are in flight. Grant for
`hw/xbox/nv2a/pgraph/vk/reports.c` (unclaimed) requested in `board-requests/accuracy804.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
