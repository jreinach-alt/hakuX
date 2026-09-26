# Audit pass 2: lane.surfwatch382 (PR #387)

Head verified: `86fcaf86a0` (remediation `13f7ec35ea`, and a prediction
file). Pass 1: `docs/audits/2026-09-26-surfwatch382-pass1.md`.

**Result: clean. MEDIUM-1 can no longer occur; LOW-2 is addressed; LOW-1 and
LOW-3 are accepted as stated. One new LOW (residual, below). Fold-ready.**

## MEDIUM-1: reordered draw marks a suspended surface dirty with no re-arm

Pass 1 asked for three checks.

**1. No path sets `draw_dirty` on a binding without the re-arm.** Every
assignment of `draw_dirty` under `hw/xbox/nv2a/pgraph/vk/`
(`grep -n 'draw_dirty\s*\(|=\|= true\|=\s*[a-z]\)'`) was read:

- The only site that sets a `SurfaceBinding`'s `draw_dirty` true is
  `surface.c:2032`, inside `pgraph_vk_surface_watch_mark_dirty`.
- `draw.c:7409-7410` set `pg->surface_color` / `pg->surface_zeta`, which are
  the PGRAPH shape state, not bindings. The watch is not on them.
- Every other site (`surface.c` 915, 980, 1583, 1784, 1868, 2141, 2148, 3611,
  4033, 4285-4286, `blit.c:628`) clears it.

`pgraph_vk_set_surface_dirty` has four callers: the reorder flush
(`draw.c:6420`), the draw-merge post-draw (`draw.c:7236`), the clear
(`draw.c:6666`) and the plain draw (`draw.c:7333`). All four go through the
two changed branches, which now call `pgraph_vk_surface_watch_mark_dirty`
whenever `color`/`zeta` is set, the only case in which the old code turned
`draw_dirty` on (`|= false` was a no-op).

**2. The race is closed, not only the common order.**
`surface_access_callback` holds `surface_watch_lock` from its `!draw_dirty`
test to `g_hash_table_add(surface_watch_suspended, …)`. `mark_dirty` holds the
same lock from `draw_dirty = true` to `surface_watch_resume`'s set lookup. So
the scenario's step 2 and step 3 are serialized. If the callback runs first,
the surface is in the set and `mark_dirty` re-arms it. If `mark_dirty` runs
first, the callback sees `draw_dirty` and does not suspend. Step 4 ("nothing
traps, stale reads until the next upload") therefore cannot happen: after
step 3 the watch is registered. `upload_pending` is correctly left set by
`mark_dirty`, as it was on master when a write trapped in the same window.

Lock order: the reorder flush runs either under pgraph.lock (pfifo) or on the
render thread. Either way `surface_watch_lock` is taken last, as in every
other path, and `surface_watch_lock` is recursive, so `register_cpu_access_callback`
re-taking it inside `surface_watch_resume` is safe. `surface_watch_resume`
only queues work (`mem_access_callback_insert`, `async_safe_run_on_cpu`) and
never waits for the vCPU, so the render thread gains no wait on the vCPU. The
upload path already called `surface_watch_resume` from the render thread, so
this is not a new thread context for it.

The gap check queued by this re-arm finds `draw_dirty` set and only counts
`lost_writes`; it cannot upload VRAM over the draw (`surface.c:1977-1982`).

**3. Wording.** The block comment at `surface.c:1888-1902` no longer says
"always"; it states the reorder case and where the invariant is now kept.
`surfwatch382-intro-ab.json`'s S1 is a registered prediction and was rightly
left unedited; NOTES sec 2 now scopes its "only path" to `draw_reorder` off
on 568332c8d2, which is how both arms ran.

The recommended arm with `draw_reorder` on is not possible: it is a Settings
switch with no env override (`SettingsActivity.kt:68`, `draw.c:31`), so a
queued request cannot set it. The lane registered
`surfwatch382-texcpu-r2.json` instead (must-not-move, default path, B =
`13f7ec35ea`); its verdict had not arrived when this pass was written. It
guards the default path only, and says so.

## LOW-2: vCPU exclusive section → pgraph.lock

Addressed: the note is at `surface_watch_rearmed` (`surface.c:1961-1965`).

## LOW-1, LOW-3

Left as pass 1 states them; the lane's NOTES sec 5 records that. Neither has a
wrong-result scenario.

## New LOW-4: a CPU read in the async re-arm window is not trapped

`surface.c:2032-2033`. The re-arm is asynchronous: the insert and TLB flush
run at the vCPU's next exit. On the reorder path the re-arm and `draw_dirty`
now happen at the same instant, so a guest read of S between the window flush
and the vCPU's next exit (the kick latency, a few TBs) is not trapped and
returns VRAM without draw N. The next read after the insert traps and
downloads, so the stale read is bounded to that window, unlike MEDIUM-1's
"until the next upload". The gap check hashes for writes only and cannot see
a read. The same window already existed on the default path (re-arm at the
upload, draw marked dirty moments later in the same hold) and is of the same
order as the `lost_writes` residual the lane documents. Behind a non-default
toggle and bounded to microseconds, so LOW. A synchronous re-arm would close
it but would add a vCPU wait under pgraph.lock, which LOW-2's note now
forbids; leaving it is the right trade.

## CI

On `86fcaf86a0`: Desktop build and NV2A index green. Android failed in
"Install the SDK components this build pins" (`NDK 29.0.14206865: Error
reading Zip content`), a download fault before any compile. The push of
this file builds a new head, and the fold gates on that run as usual.
