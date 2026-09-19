# lane.diagdump77 -- a marker-file-armed frame dump that does not serialize

Issue: #77. Base: master @ ab471cc80f. PR #143.

## What this lane is for, in one line

#77 is blocked on a *capability*, not on an analysis: the only per-draw frame
dump this emulator has is reachable from the Debug Capture button and calls
`pgraph_vk_finish` before every draw, so it is blind to exactly the behaviour
a subtle stipple needs visible -- draw merging, deferred submission, barriers.
This lane adds a second instrument with a different trigger and no per-draw
finish, and takes one run with it. It does **not** diagnose the stipple.

## What the existing path does (read, not assumed)

- `nv2a_dbg_trigger_diag_frames()` (hw/xbox/nv2a/pgraph/vk/renderer.c:555) is
  called from exactly one place: `nativeDumpDiagFrames`
  (android/app/src/main/cpp/xemu_android.cpp:1457), a JNI entry point on
  `MainActivity`. There is no file, env var or property that reaches it.
- `nv2a_diag_log_draw_call()` (renderer.c:1049) calls
  `pgraph_vk_finish(pg, VK_FINISH_REASON_SURFACE_DOWN)` **per draw**, to make
  `diag_download_surface` safe. That finish flushes the draw queue and the
  reorder window (vk/draw.c:3188-3217), so under a diag capture no draw is
  ever merged with the one after it and no barrier behaviour survives to be
  observed. This is the blindness #77 names.
- The serialisation also reaches further than merging: texture reuse is keyed
  on `submit_time` against `submit_count` (vk/texture.c:2074), and under a
  per-draw finish that counter advances once per draw.

## What was built

`hw/xbox/nv2a/pgraph/vk/renderer.c`, one self-contained section:

- **Arming.** A marker file `frame_dump.on` in the app's external files dir,
  polled once a second at the flip. Same directory and same idea as apu.c's
  PCM capture marker, for the same reason: the existing trigger is a button,
  and a soak has nobody to press it. `XEMU_FRAME_DUMP=<spec>` arms at startup
  instead, which is what `request.sh --env` can set today.
- **Spec tokens** on the marker's first line: frame count, `noimages`,
  `capNN` (MB), `afterNN` (start NN seconds after the arm is *seen*), `diag`
  (also run the old capture, as the serialising control arm).
- **Per draw:** no Vulkan call of any kind. One buffered `fprintf` of host
  state -- registers, bindings, and the scheduler's counters (`in_command_
  buffer`, `draws_in_cb`, `submit_count`, draw queue and reorder window
  counts), plus each stage's bound `VkImage` handle, which is what a stale
  binding would show up in.
- **Per frame:** the display surface, read out of guest VRAM at flip_stall
  *after* the flip's own `pgraph_vk_finish` has already run, so it adds no
  synchronisation. One PPM per frame, named next to the records.
- **Output:** `framedump_<id>.jsonl` + `framedump_<id>_fNNN.ppm` in the files
  dir, so `--pull 'framedump_*'` collects the lot.

`docs/lanes/diagdump77/framedump_check.py` reads a dump and says whether it
serialised; `framedump_check_selftest.py` builds both arms synthetically and
asserts the checker separates them (the serialising mutant must trip it, or
the "NOT SERIALISED" verdict is free).

## How the claim is falsifiable from the artifact alone

The dump records two independent readings of the same fact, per draw:

| column | under the Debug Capture button | under this path |
|---|---|---|
| `cb_draws` (`r->draws_in_cb`) | never exceeds 1 -- the finish submits the command buffer at every draw | climbs across the frame |
| `submits` (`r->submit_count`) | +1 per draw | flat between flips |

So no external trace is needed and none is cited: the file says which
instrument produced it. `framedump_check.py` prints both and refuses to
average them -- a build that moved one and not the other is a broken
instrument, not a pass.

## What it cannot see -- read this before citing a null result

- **No per-draw image.** Reading a surface back mid-frame is precisely what
  forces the finish. Per draw you get state and schedule; per frame you get
  the picture. A draw-level *pixel* attribution still needs the old path,
  with the old blindness.
- **No clears or blits.** Those hooks are gated on
  `nv2a_dbg_diag_frame_active()` at their call sites in `vk/draw.c:6711` and
  `vk/blit.c:450`, files this lane does not hold. Draws only.
- **Nothing about merging when merging is off.** `draw_merge` and
  `draw_reorder` are prefs defaulting false (vk/draw.c:32,
  SettingsActivity.kt:68). The session header records both and the checker
  prints a scope note, because a dump taken with them off says nothing about
  merged draws. What it *does* show with them off is deferred submission and
  command-buffer batching, which are on by default -- and those are enough to
  break the "one submit per draw" schedule the old capture imposes.
- **Its own timing cost.** One buffered `fprintf` per draw and one ~900 KB
  PPM write per frame, on the pgraph thread, to FUSE-backed storage. That is
  far cheaper than a fence wait per draw but it is not free; a frame-time
  measurement taken during a dump describes the dump.

## The gap that is left, and who can close it

Nothing in the dispatch path can touch a file on the device mid-run:
`request.sh` has `--audio-capture` (which `soak_title.sh` turns into a marker
write) but no equivalent for this, and neither file is in this lane's grant.
So on-device arming today goes through `--env XEMU_FRAME_DUMP=...,afterNN`,
which runs the *same* code from one branch earlier. The marker `fopen`/
`unlink` branch is exercised by reading and by the desktop path, not by a
queued soak.

**The ask for whoever holds the harness files:** a `--frame-dump SPEC` flag on
`request.sh` that `soak_title.sh` turns into
`echo SPEC > $GUEST_FILES/frame_dump.on` at a chosen offset into the run --
the audio marker's own shape, including deleting the previous dump first. That
makes the marker trigger reachable from the queue and lets a dump be armed on
a scene rather than on a stopwatch.
