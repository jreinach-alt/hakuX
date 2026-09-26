# lane.surfwatch382 -- suspend the CPU-access watch on a surface that owes no download (#382)

Base master 6c25a829ef. One file: `hw/xbox/nv2a/pgraph/vk/surface.c`. Read
`docs/lanes/fps382/NOTES.md` sec 2, 2b and 2c first; this lane implements the
hunk 2c names.

## 1. The hunk

The watch on a bound surface makes every page under it `TLB_FORCE_SLOW`, so
every guest store traps into `surface_access_callback`. That walks the
callback list, takes `pgraph.lock`, walks the surfaces, and ends in a
`tlb_set_dirty` that cannot clear. After the first write to a surface that
owes no download, each later trap only sets `upload_pending` again.

- **Suspend** (`surface_access_callback`): on a write to a surface that is not
  `draw_dirty`, set `upload_pending`, `unregister_cpu_access_callback`, and add
  the surface to `surface_watch_suspended`. A surface that is `draw_dirty` is
  not suspended on that write. Its download runs first, and the next write
  after the download suspends it. So `draw_dirty` with
  `download_generation == draw_generation` also counts as "owes a download"
  here. That state is transient (every full download clears `draw_dirty`
  along with it), and treating it as owing costs one extra trap.
- **Re-arm** (`pgraph_vk_upload_surface_data`): if the surface is suspended,
  re-register the watch before VRAM is read. `upload_pending` is cleared under
  the same lock.
- **Why the upload is the only re-arm site.** Nothing but the upload clears
  `upload_pending` (grep: `surface.c` 2989; 3937 is the unshelve path, and
  shelving already dropped the surface from the suspended set via
  `unregister_cpu_access_callback`). Every draw and clear runs
  `pgraph_vk_surface_update(upload=true)` first (draw.c 1188, 7086), which
  uploads a bound surface whose `upload_pending` is set. So the watch is live
  before the GPU can make the surface owe a download, and draw.c needs no
  change. A CPU read of a suspended surface has nothing to download.
- **Suspended set, not a flag.** `SurfaceBinding` is in `renderer.h`, which
  this lane was not granted, so `watch_suspended` is a pointer set in
  surface.c. Every retire and free path goes through
  `unregister_cpu_access_callback`, which removes the surface from the set.
  So a freed or recycled binding never stays in it.
- **Locking.** `access_cb` and the set are touched on three threads: the vCPU
  in the callback, the pfifo thread under `pgraph.lock`, and the render
  thread. The render thread uploads the display surface in `render_display`
  without `pgraph.lock` (RCMD_PROCESS_PENDING; the pfifo thread waits on it
  while holding only `pfifo.lock`). A `QemuRecMutex surface_watch_lock`
  guards them. The lock order is always `pgraph.lock` then
  `surface_watch_lock`, and nothing holds the watch lock while it waits for
  anything.
- **Instrument.** `[surfwatch382] suspended= suspends= rearms= gap_writes=
  lost_writes=` prints beside `[watch311]` every 5 s.

## 2. The race, decided: closed by a hash check, not by run_on_cpu

`mem_access_callback_insert` is asynchronous: the insert and its TLB flush
are queued as safe work on the vCPU. A store that lands between the upload's
VRAM read and that work would be missed. A synchronous re-arm (`run_on_cpu`)
can deadlock. The uploader holds `pgraph.lock`, and the vCPU can be blocked
in `surface_access_callback` waiting for it (another surface's trap), so it
never reaches the work the uploader is waiting on.

So the upload hashes the surface's VRAM just before it reads it. It then
queues a safe-work item behind the insert and the flush, which run in FIFO
order. The item runs on the vCPU with the watch live. It re-hashes the same
range under `pgraph.lock` and the watch lock:

- Same hash: nothing was written in the gap.
- Different hash, surface not `draw_dirty`: the guest wrote in the gap. Set
  `upload_pending`, which is what a trapped write would have done. Counted as
  `gap_writes`.
- Different hash, surface `draw_dirty`: the GPU drew after the upload and the
  guest also wrote in the gap. Setting `upload_pending` would put VRAM over
  the draw, so the item only counts it, as `lost_writes`. This is the one
  residual. It needs a guest store to a render target in the microseconds
  between that target's upload and the vCPU's next exit, and a draw to the
  same target recorded in between. The arm's S1 leg reads `lost_writes`.

The item matches the arming that queued it by `access_cb` pointer. That
pointer cannot be freed before the item runs, because its removal can only be
queued after the item (both are queued under the watch lock). The hash is
over VRAM before the read, not after, so a store between hash and read is
seen as a change. The cost is one extra re-upload, not a missed write.

Hash cost: two passes over 1.2 MB per displayed movie picture (4-lane
multiply chain), against about 238,000 trapped stores per displayed picture
on master.

## 3. Arms (registered before any device run)

- `docs/testing/predictions/surfwatch382-intro-ab.json`: the soak pair,
  judged by `abjudge.py` here. The arms job skips soaks, so this lane queues
  both arms with `request.sh` (Nova, perflog, 240 s, frames every 10 s).
- `docs/testing/predictions/surfwatch382-texcpu.json`: the must-not-move
  suites, Texture_CPU_Update and Texture_render_update_in_place, queued by the
  arms job.

`abjudge.py` run on two master soaks (titlebench-9r against fps382's perflog
run) gives fps B/A = **1.53 over 58-172 s with no code change** (10.46 against
16.04). So the brief's 1.5x ratio leg cannot separate on its own. The
deciding legs are P1 (B's slow stores <= 50,000/s, where master is 2.5-2.7M/s
on every run) and P4 (B's fps over 62-140 s >= 20, a level no master run has
reached; max 16.07).

## 4. Results

(pending)

## Do not repeat

- Do not judge this fix on the fps ratio alone (sec 3).
- Do not re-arm synchronously with `run_on_cpu` from the uploader (sec 2).
- Do not take `pgraph.lock` in the display-path upload to guard `access_cb`.
  `render_display` runs on the render thread without it, and the pfifo thread
  is parked waiting for that thread.
