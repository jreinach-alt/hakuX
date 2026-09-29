# Audit pass 2: PR #572, lane.pacing (lane/pacing-spin)

Head verified: fe9784bcfb (the pass-1 audit commit on 9c0949366a). No code
commit has landed since pass 1: `git diff 9c0949366a fe9784bcfb -- hw/` is
empty. The PR is MERGEABLE and CI is green (both build jobs and check).

**Result: clean. Pass 1 found no HIGH or MEDIUM. Its four LOWs stand as
LOW, and none of their scenarios can fire in this tree.**

## Each pass-1 finding, re-checked

### L1: a lost set through a concurrent `wait_idle` reset: cannot occur today

The scenario needs a second thread, outside the render-thread context, to
reset `idle_event` in `pgraph_vk_render_thread_wait_idle` while the PFIFO
thread blocks in `wait_frame_submitted`. I listed every caller again on this
head:

- `draw.c:1620`, `draw.c:3402`, `command.c:108` (`end_single_time_commands`):
  pgraph code, reached on the PFIFO thread, or on the render thread, where
  `wait_idle` returns at once (`is_render_thread_context`).
- `display.c:1851`: runs inside the render thread, so it returns at once.
- `render_thread.c:406` (`shutdown`): teardown, after pgraph stops issuing
  finishes.
- `render_thread_enqueue` callers (`draw.c:3905`, `renderer.c:557`): enqueue
  only. They never reset the event.

So the event has a single resetter outside the render thread, and that
resetter is the waiter itself. The scenario needs a thread that does not
exist. The code comment at draw.c:3467-3469 still describes `wait_idle` "on
another thread" as possible. The hang pass 1 describes would become real on
the day a second resetter appears. This stays LOW and latent. It does not
block the fold. If the lane or a later change adds one, the fix is the one
pass 1 suggested: use a bounded `qemu_event_timedwait` in the block loop.

### L2: unsynchronized `rwait526` counters: stands as LOW

The effect is limited to diagnostics: at most a count or two per 10 s window
in the measured runs. No behaviour depends on these counters.

### L3: instrumentation in the release path: stands as LOW

This is lane scaffolding: one `get_clock()` per finish, two thread-CPU reads
per non-immediate wait, and a 10 s log line on Android. It should be removed
or gated when #526 closes.

### L4: stale PR body: stands as LOW, and it does not reach master

The body still says "This PR stays a draft until they are read" about the
Otogi 400 s runs. The fold is a `git merge` of the lane branch, not a squash
using the body, so the body does not become the commit record. The Otogi read
is in the tree, in `docs/lanes/pacing/NOTES.md` at 9c0949366a, and on the PR
in the lane's 2026-09-29T10:54Z comment: all four runs valid, P2 holds, H1
holds at 0.23 against 0.25. The fold record is therefore complete without the
body.

## Not an audit finding, recorded for the board

`[job.arms]` refused `pacing-rwait-otogi.json` because `a_ref == b_ref`.
That registration is an A/B on one binary with the env as the variable, and
the lane already read its runs by hand. The pixel arm this PR depends on
(01e62d8d1c vs f53000f7e4) is a PASS, and the PR carries `verified`.

## Verdict

Clean. Moving the PR to `fold-ready`.
