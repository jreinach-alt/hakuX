# lane.doa413b -- #413 DOA2U surface_update cost

Base: master @ 7e6a4ac88a, then merged origin/master f63be3d4ab (2026-09-26) and
origin/lane/blinx372d (#396, still open; vk/surface.c is released to this lane at ready).

## Why attempt 1 did not finish

Attempt 1 built the probe (e38f95712e), pushed it, queued the pilot soak
`1790456253-doa413b-520408` (Nova, perflog, `survey` route, 300 s, ref e38f95712e), and then
ended without a `waiting:` comment. The soak was still in the queue with 9 requests ahead of it
when attempt 2 started (21:48Z). So attempt 1 was waiting on a device request, and it did not say so.

## What the probe logs (e38f95712e)

`LOGCAT_SPEC_OVERRIDE` is an environment variable of the dispatcher process only. A request
cannot carry it, so a pilot could not get `xemu-surf:I` from the request. The probe avoids
that: it prints under tag `hakuX`, which every spec carries, with prefix `[surf413]`, once per
60 guest frames (perflog builds only):

- `pre / flush / part / cdef / upl / exp / prn / tail`: wall ms/frame per segment of
  `pgraph_vk_surface_update`. `fin` is the `pgraph_vk_finish` time nested inside those
  segments, so `sum - fin` is what `Surf` reports.
- `realupl / uplKB`: bound surfaces whose `upload_pending` was set, meaning real uploads, not
  the early return.
- `hash / hashKB`: whole-surface hashes taken by `surface_watch_resume`.
- `active / shelved / invalid`: the length of each list, which bounds the linear scans in
  `expire_old_surfaces`, `prune_invalid_surfaces` and `pgraph_vk_surface_get`.
- A second line, `[surf413] xemu-surf ...`, carries profile.c's own sub-split (populate,
  dirty, enrp, lookup, create, bind, upload, download, expire).

The dispatcher.sh hunk adds `xemu-surf:I` to the default spec. It only takes effect after the
host runs its dispatcher update window.

## Candidates, read from the code before the price (not a site yet)

The fight's calls are almost all `upload=true`, from draw.c:1188 and 7096. The `upload=false`
path is only reached from blit.c. At 700 calls/frame and 45 ms, each call costs about 64 µs.
But the shape changes happen only about 6 times per frame, so if the cost sits in them it is
about 7.5 ms per change. That points at work proportional to surface size, not at per-call
overhead:

1. A real upload for each rebind: `upload_pending` set again by the CPU-access callback, then
   `surface_watch_resume` hashes the whole surface plus the CPU conversion or copy
   (`upl`, `realupl`, `hash`).
2. `update_surface_part` creating a new surface for each rebind instead of finding the old one
   (`part`, and xemu-surf `create` against `hit`).
3. `expire_old_surfaces` / `prune_invalid_surfaces` scanning on every call (`exp`, `prn`, the
   list lengths). This is per call, so it would need long lists to reach 64 µs.
4. `complete_deferred` waiting on a fence (`cdef`, `fin`).

The dirty-bitmap scan in `update_surface_part` is `!tcg_enabled()` only, so it does not run on
Android.

## Why attempt 2 did not finish

Attempt 2 (started 21:48Z) found the pilot still queued behind 9 requests, wrote the notes above
(20ae133d4c), and ended without a `waiting:` comment again. The pilot then ran (15:11-15:17 PDT)
and `handback.sh` resumed this lane as attempt 3 at 22:17Z.

## Pilot `1790456253-doa413b-520408`: the price

The pilot is valid. It ran on the Nova, apk 24fd1f4b1297 = e38f95712e, perflog, `survey` route, 300 s.
Every 60 frames it printed a `[surf413]` line and an `[surf413] xemu-surf` line, 111 of each. The
route reached a fight at about 15:15:05, and gfps then held at 11-15 for the last ~110 s. That is
slightly worse than doa413's 14-16; the probe itself costs well under 1 ms/frame (the `pre`/`tail`
columns).

| window (60 frames each) | gfps | Surf | pre | part | cdef | upl | exp | prn | fin | realupl | hashKB | active/shelved/invalid | GPU | Fin(Sub/Fen) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| menus, boot (15:12:01) | 59 | ~1.8 | 0.00 | 0.55 | 0.87 | 0.38 | 0.01 | 0.00 | 0.57 | 15 | 0 | 3/0/11 | | |
| fight, 15:15:20-15:16:52 (20 lines) | 11-15 | 61-63 | 0.03-0.04 | 0.34-0.39 | **51.1-58.9** | 0.10-0.12 | 0.07-0.08 | 0.04-0.05 | **0.00** | 0 | 0 | 6/0/10 | 40.5-48.3 | 2.3-12.7 |

The xemu-surf split agrees: `dfF` (the fence wait inside `complete_deferred`) is 36.5-61.9 ms/frame,
`dfR` (the staging-to-VRAM copy) 0.2-0.6, and populate, dirty, lookup, create, bind and upload are
0.0-0.1 each. The loop makes about 1450 `upload=true` calls per 60 frames (~25/frame), 45 downloads
per 60 frames, and there are no creates and no evictions.

**The priced site is `pgraph_vk_surface_update()` -> `pgraph_vk_download_surface_complete_deferred()`
(vk/surface.c, the call between `part` and `upl`). Lookup, bind, upload and expire are not it.** `fin`
is 0, so it is not a `pgraph_vk_finish`. It is one of the two `vkWaitForFences` branches. The batch
it waits on is the one the flip pre-records (`pgraph_vk_prerecord_display_download`, renderer.c
flip_stall -> `FLIP_STALL` finish): the display surface plus every other dirty surface, copied in
the command buffer that carries the whole frame. The first `surface_update` of the next frame
completes that batch, so the renderer waits until the GPU has drained frame N before it records
frame N+1. That also explains why it grows with the fight. The cost per call is not the issue; the
wait is one per frame, and it is as long as the GPU frame (40-48 ms by timestamps, plus queueing).
In light play the GPU is done before the CPU asks, and the same wait costs ~0.

None of the four candidates from the code survived the numbers. `realupl`=0, `hashKB`=0, the lists
hold 6/0/10 surfaces, and `part`, `exp` and `prn` are under 0.4 ms.

## The cut (this PR)

Lazy completion, `XEMU_SURF_LAZY_COMPLETE` (default on; `=0` restores the old call). In an
`upload=true` surface_update, a batch that is already submitted is no longer completed. It is left
to whatever reads VRAM next, and each such reader now completes it first:

- `pgraph_vk_upload_surface_data` (VRAM to GPU). This covers the #11 unshelve case.
- `download_surface_record_deferred`, so that one batch never spans two fences.
- `pgraph_vk_prerecord_display_download`, at the next flip. This is where it normally lands: one
  frame of CPU/GPU overlap.
- Readers that already completed first: guest CPU access (`process_pending_downloads`), and blit,
  vertex and texture reads (`download_surfaces_in_range_if_dirty`).
- The frame ring, when it reuses the slot (draw.c already calls `complete_staged_downloads` there).

Two follow-on fixes, both only when the flag is on:

1. The display-surface tail in `complete_deferred` set `draw_dirty=false` and
   `download_generation = draw_generation`. That is only true if no draw landed after the flip. Under
   lazy completion draws do land, so the tail now just clears the flags, and the generation is the
   one `complete_staged_downloads` retired from the copy's own `draw_generation`.
2. The ring drain leaves `display_predownload_pending` set with no batch, which would stop every
   later flip from pre-recording. `display_predownload_forget_if_drained` clears it.

The upload=false path (blit.c) still completes as before.

Expected: the fight goes from serial CPU+GPU (~76-86 ms) toward max(CPU ~20-25, GPU 40-48), i.e.
roughly 20-24 fps, not 30. The GPU in this fight is 40-48 ms, not the ~33 doa413 read. `[lazy413]
enabled= skips= reads=` prints every 5 s in every build, so an arm can show the path fired.

## Status

Type-checked with the NDK clang line from the shared tree's compile database, perflog on and off: 0
errors. There is no desktop build on this host (AGENTS.md's known gap). Next: a same-APK Nova A/B
(`XEMU_SURF_LAZY_COMPLETE=0` vs default) of the pilot route, and the pgraph must-not-move arm.
