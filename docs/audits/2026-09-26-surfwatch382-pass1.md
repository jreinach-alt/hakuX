# Audit pass 1: lane.surfwatch382 (PR #387)

Diff read: `origin/master...961fb52c99`, 5 files. The only code is
`hw/xbox/nv2a/pgraph/vk/surface.c` (+169), all in 568332c8d2. The later
commits touch only the NOTES, `abjudge.py` and the two prediction files, so
both registered arms measure the code under review. CI is green and the PR is
mergeable.

**Result: 1 MEDIUM, 3 LOW. Needs remediation.**

## What the hunk claims

The first guest write to a surface that owes no download (`!draw_dirty`)
suspends that surface's CPU-access watch. Its correctness rests on one
invariant, stated in the block comment at `surface.c:1888-1895`:

> A GPU draw is always preceded by that upload
> (`pgraph_vk_surface_update(upload=true)` runs before every draw and clear),
> so the watch is live again before the surface can owe a download.

I checked the rest and found no defect: the lock order is always pgraph.lock
then `surface_watch_lock`, and the second lock is a leaf. Removal and insert
are both queued work, so the callback can unregister its own watch. The
pointer compare in `surface_watch_rearmed` cannot hit a reused address,
because the removal is queued after it. Every retire and reuse path goes
through `unregister_cpu_access_callback`, including the unshelve assignment
at `surface.c:3923`, and that call empties the suspended set. The gap check
runs after the insert and the synced flush in the same work queue.

The invariant is the weak point.

## MEDIUM-1: with draw reordering on, a draw marks a suspended surface dirty with no upload, so a CPU read gets no download

`surface.c:2087` (the suspend), `draw.c:6420` (`flush_reorder_window_internal`)

The invariant holds when `pgraph_vk_set_surface_dirty` runs in the same
pgraph.lock hold as the `surface_update(upload=true)` that came before it.
The callback also needs pgraph.lock, so it cannot suspend between the two.
The draw reorder window breaks this. `pgraph_vk_draw_end` (`draw.c:6473-6519`)
snapshots the draw into `r->reorder_window` and returns. `draw_dirty` is set
only when the window is flushed (`draw.c:6420`). That can happen in a later
method, after pgraph.lock has been released, or on the render thread
(`render_thread.c:273,316`). Neither path runs an upload for the binding
first.

Failure scenario, with `draw_reorder` on (a Settings switch and a per-game
setting: `SettingsActivity.kt:541`, `PerGameSettingsActivity.kt:102`):

1. Draw N begins. `surface_update(upload=true)` uploads colour binding S.
   `upload_pending` is cleared, the watch is live and S is not `draw_dirty`.
   Draw N is queued in the reorder window and pgraph.lock is released.
2. The guest CPU stores to S. The watch traps and `surface_access_callback`
   sees `!draw_dirty`, so it sets `upload_pending`, **unregisters the watch**
   and adds S to the suspended set.
3. The window flushes, for example on the render thread's `RCMD_FLUSH`.
   `pgraph_vk_set_surface_dirty` sets `S->draw_dirty` and bumps
   `draw_generation`. No upload runs, so the watch stays down.
4. The guest CPU reads S. Nothing traps, so no download is queued, and the
   guest reads VRAM without draw N's pixels. It keeps reading stale VRAM
   until the next `surface_update(upload=true)` on S re-arms the watch. That
   upload then writes VRAM over draw N, because `upload_pending` is still
   set.

Before this change, step 4 trapped and downloaded draw N, as the watch was
never down. The fix is what turns a CPU read after a reordered draw into a
stale read.

`gap_writes`/`lost_writes` do not count this path. S1 in
`surfwatch382-intro-ab.json` ("the only path by which a partly written
picture can persist") is therefore too broad. It is true only while
`draw_reorder` is off.

Blast radius: `g_xemu_draw_reorder` defaults to false on desktop and on
Android (`draw.c:31`, `SettingsActivity.kt:68`). No registered arm ran with
it on, so neither PASS covers this. The code is wrong outside what the
goldens exercise, but only behind a user toggle, so MEDIUM, not HIGH.

Remedy, either of:

- Do not suspend while a reorder window is open
  (`r->reorder_window.count > 0` in the suspend condition at
  `surface.c:2087`).
- Better: restore the invariant where it breaks. When
  `pgraph_vk_set_surface_dirty` makes a binding `draw_dirty` and that
  binding is in the suspended set, re-arm it (`surface_watch_resume` under
  `surface_watch_lock`). The watch is then live whenever a download is owed,
  whatever path made the surface dirty.

Also correct the block comment's "always", and correct S1's wording or scope
it to `draw_reorder=false`.

The draw-merge queue does **not** have this problem. Its queued draws `goto
post_draw` and call `set_surface_dirty` in the same hold (`draw.c:7070-7090`).

## LOW-1: the gap check hashes the whole surface a second time with the vCPU stopped

`surface.c:1954` (`surface_watch_rearmed`), `surface.c:1992`

Each re-arm hashes the surface once on the uploading thread and once in an
`async_safe_run_on_cpu` exclusive section. For the 640x480x32 surface in the
motivating case that is 1.2 MB per hash, which is two scans per
CPU-write-then-upload cycle, one of them while the guest is stopped. The soak
shows a net win for 50 Cent. A title that uploads a larger suspended surface
many times per frame would pay it again each time. No scenario gives a wrong
result, so this is LOW. Possible narrowing: hash only once the watch has
actually been down, or sample by page.

## LOW-2: new lock edge from the vCPU's exclusive section to pgraph.lock

`surface.c:1959`

`surface_watch_rearmed` takes pgraph.lock inside safe work: the vCPU is
exclusive and the BQL is dropped. I found no deadlock. Nothing in `hw/xbox`
calls a synchronous `run_on_cpu`, `start_exclusive` or `cpu_exec_start`, so
no holder of pgraph.lock waits on the vCPU. It is still a new dependency. A
one-line note at the function would stop a later change from adding a
synchronous vCPU wait under pgraph.lock.

## LOW-3: a gap write can re-upload VRAM changed by something other than the guest

`surface.c:1965`

The gap check treats any VRAM change as a guest write. A PGRAPH blit or an
overlapping surface's download that lands in the gap changes the hash too.
That makes `upload_pending` fire and forces one extra upload of VRAM that is
already current. The cost is one redundant upload. The `gap_writes` counter
also overstates guest writes, so read it as an upper bound.

## Verification pass 2 should do

- MEDIUM-1: confirm that with `draw_reorder` on, no path can set
  `draw_dirty` on a surface in `surface_watch_suspended` without a re-arm.
  Enumerate every `pgraph_vk_set_surface_dirty` caller and every direct
  `draw_dirty =` / `|=` site. Confirm the block comment and S1 no longer say
  "always" / "only". A registered arm with `draw_reorder` on, over the two
  texture suites in `surfwatch382-texcpu.json`, would show the fix is not
  inert. That is recommended, not required.
