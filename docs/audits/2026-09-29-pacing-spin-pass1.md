# Audit pass 1: PR #572, lane.pacing (lane/pacing-spin)

Head audited: 9c0949366a. Base 01e62d8d1c. The code under audit is
`hw/xbox/nv2a/pgraph/vk/draw.c`. It is unchanged since f53000f7e4, the ref
every arm ran on (`git diff --stat f53000f7e4 HEAD -- hw/` is empty). Master
has moved 193 commits since the base but changes nothing in the wait
machinery: no `idle_event`, `wait_idle`, `render_thread_enqueue`,
`frame_submitted`/`frame_enqueued` or `sched_yield` line in
`hw/xbox/nv2a/pgraph/vk/` differs between 01e62d8d1c and origin/master. The
PR is MERGEABLE and CI is green.

**Result: no HIGH, no MEDIUM, four LOW.**

## What was checked

1. **Correctness of the block path (`wait_frame_submitted`)**. The waiter
   resets `idle_event`, re-reads `frame_submitted[frame]`, and only then
   waits. The render thread stores `frame_submitted` in `process_finish`
   (render_thread.c:153), before the `qemu_event_set` at the end of the
   command (render_thread.c:347), and `qemu_event_set` has a full barrier.
   So a submit that lands after the re-read is always followed by a set that
   comes after the reset. No wake-up is lost to the waiter's own reset.
2. **The awaited submit is always still queued or done.** At the deferred
   site the FINISH was enqueued just before the wait. At the rotate site
   `frame_enqueued[next]` is true only between the enqueue and the rotation
   that clears it (draw.c rotation, `flush_all_frames` and `finalize` clear
   it only after `wait_idle`). `process_finish` sets `frame_submitted`
   unconditionally after `VK_CHECK(vkQueueSubmit)`. Nothing waits on a flag
   that nobody will set.
3. **The submit worker also sets `frame_submitted`** (submit_worker.c:61) but
   never sets `idle_event`. It is dead code: nothing calls
   `pgraph_vk_submit_worker_init` or `_enqueue`. This is not a finding, but
   anyone who turns the worker on must also make it set `idle_event`, or
   this wait never returns.
4. **The render thread can never block on its own event.** Every call from
   render_thread.c into pgraph code is bracketed by
   `is_render_thread_context = true`, and that case takes the old
   `sched_yield` loop. This is the same behaviour as before for a PRESENTING
   finish that rotates on the render thread.
5. **Rotate-site guard change.** The old code tested
   `frame_enqueued && !frame_submitted`. The new code calls the function
   whenever `frame_enqueued` is true, and the function returns early when
   the slot is already submitted. The two are equivalent, apart from one
   `get_clock()` and a counter.
6. **Non-Android builds.** `rwait_pct_us` and the log print are under
   `__ANDROID__`. The rest compiles on all hosts (CI build green on both
   jobs).
7. **Histogram bounds.** `dt` comes from a monotonic clock and is never
   negative. The bin index is clamped with `MIN(dt / RWAIT_BIN_NS,
   RWAIT_BINS)`, and the array has `RWAIT_BINS + 1` entries.

## Findings

### L1: a set can be lost from the waiter's side, through the reset in `wait_idle` (LOW, latent)

`qemu_event_wait` in this tree loops (util/event.c:135): when it wakes and
finds the event FREE again, it goes back to sleep. The PR handles one
direction: the waiter's reset swallowing a set that `wait_idle` needed, fixed
by the trailing `qemu_event_set`. It does not handle the other direction.

Scenario: the render thread finishes the awaited FINISH and sets the event
(render_thread.c:347). It finds its queue empty, sets it again (:212) and
sleeps on its cond. Before the woken waiter reloads the value, a thread in
`pgraph_vk_render_thread_wait_idle` wakes, resets the event, sees an empty
queue and returns. The waiter reloads FREE, goes back to sleep, and no
further set comes until someone enqueues.

No such concurrent thread exists today. Every caller of `wait_idle` or
`render_thread_enqueue` outside the render-thread context is on the PFIFO
thread, which is the waiter. `display.c:1851` runs inside the render thread,
where `wait_idle` returns at once. So there is no concrete failure today, and
the finding is LOW.

The code comment and the PR body do describe `wait_idle` "on another thread"
as a live possibility. If that premise ever becomes true, this path can hang
the PFIFO thread. Suggested fix, not required: bound the wait with
`qemu_event_timedwait` (for example 1 ms) and re-check, or state the
single-resetter invariant in the comment.

### L2: the `rwait526` counters are shared across threads without synchronization (LOW)

The PFIFO thread and the render thread (a PRESENTING rotate) both increment
`rwait526.*`, and either can `memset` it in `rwait_report`. A window can
lose or tear counts, or print `p50/p99 = -1` when `waits` exceeds the
histogram sum. This affects only the diagnostic, but it is the diagnostic
the lane's legs are judged on. Across the measured runs its size is at most
a count or two per 10 s window.

### L3: the instrumentation ships in the release path (LOW)

Every `pgraph_vk_finish` that reaches a wait site now pays a `get_clock()`.
Every non-immediate wait pays two `CLOCK_THREAD_CPUTIME_ID` reads, which are
syscalls on Linux, not vDSO calls. An Android build also emits a
`[rwait526]` line every 10 s for the life of the process. The cost is small
next to what the change removes. It is still lane scaffolding and should be
removed, or put behind the env switch, once #526 closes.

### L4: the PR body is stale (LOW)

The body says "This PR stays a draft until they are read" about the Otogi
400 s runs. The PR is no longer a draft, and 9c0949366a records the Otogi
read in NOTES ("every safety leg holds, P2 at the cap only"). The body
should carry that result, so the fold record is not left with the Otogi leg
reading as still open.

## For pass 2

Nothing is HIGH or MEDIUM. Pass 2 should confirm:

- L1 is either bounded (a timed wait) or documented as a single-resetter
  invariant.
- L4: the body reflects the Otogi read.

L2 and L3 may stand as LOW, provided the lane says so.
