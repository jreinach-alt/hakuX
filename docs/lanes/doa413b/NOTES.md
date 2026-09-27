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

## Attempt 3 ends waiting (2026-09-26 ~22:40Z)

The cut is committed at 7f01f7f157, and the arm is registered at 7c0dc74319
(`doa413b-lazy-mnm.json`, 0d5f93f210 vs 7f01f7f157). preflight passes. The lane is waiting on
three things outside this session:

- Soak arm A `1790461490-doa413b-542947` (`XEMU_SURF_LAZY_COMPLETE=0`) and arm B
  `1790461494-doa413b-546424` (`=1`). Same APK, Nova, perflog, survey route, 300 s. At queue
  time about 115 queue entries were ahead of them, and a Nova hold was in force.
- The pgraph must-not-move arm, which the arms job runs from the committed prediction.

How to read them on resume: take each soak's gfps and `[surf413] cdef` over the fight lines (gfps
under 20 after the route's `mark play` at about 15:16 in the pilot's timeline, i.e. the last ~110 s).
Report the median per arm, and check `[lazy413] skips` > 0 in B and `enabled=0` in A. For the arm,
read the `[job.arms]` verdict, B's `[lazy413] skips`, and every scores1.tsv `status` for
`unreadable`. If the arm fails, set the default to off (`enabled = env && env[0] == '1'`) and say
why in the A/B.

## Why attempt 3 did not finish

Attempt 3 ended waiting, correctly, on the soak pair and the arm, but its soak requests pinned
`--device thor`. The Thor has no DOA2U, so both errored at once ("title not on device") and
measured nothing. The arm ran. Attempt 4 (this one) re-queued the pair on the Nova.

## Must-not-move arm: PASS (Thor, 1790463182-arms-doa413b-base/-fix, 0d5f93f210 vs 7f01f7f157)

- 206 captures per leg, the same keys. Status is `ok` 201 / `white-content` 5 in both legs, and
  no `unreadable`.
- 205 of 206 captures score identically. The one that moved is `Blend_surface/R5G6B5_Add_SrcA_DstA`
  (white-content in both legs, 14833/239 -> 11964/33). Its fix capture (sha256 110b0261177c) is
  byte-identical to the BASE legs of `arms-zrtz272` and `arms-pshqueue` (both legs). So it is a
  known noise state of that row, not this change. The base capture 30aaeba84f30 is the row's
  commonest state (61 dirs).
- B's logcat: `[lazy413] enabled=1 skips=1 reads=0`. The lazy path fired once, so the arm is not
  inert, but it is thin: the test discs rarely leave a batch submitted across a surface_update.
  The soak is where the path does real work.
- So the default stays ON.

## A/B soak pair, attempt 4 (queued 2026-09-26, Nova)

`1790473771-doa413b-1386898` (A, `XEMU_SURF_LAZY_COMPLETE=0`) and `1790473773-doa413b-1387399`
(B, `=1`). Both are same APK 7f01f7f157, perflog, survey route, 300 s. Read them as the attempt 3
section says: fight-window median gfps and `[surf413] cdef`, `[lazy413] enabled=0` in A and
`skips>0` in B. If B does not beat A, the price stands, but the cut is refuted. Then set the
default off and name the next lever on #413: the GPU's own 40-48 ms.

Merged origin/master at 2026-09-26 (#396 had folded), so the blinx372d files left this PR's diff.

## Why attempt 4 did not finish

Attempt 4 re-queued the soak pair on the Nova, posted a `waiting:` comment naming it, and ended.
That was correct. While it waited, the arms job judged the first arm FAIL on the known-noise row
(`Blend_surface/R5G6B5_Add_SrcA_DstA`, see above) and labelled the PR `regressed`. The soak pair
finished at 20:12 and 20:20 PDT, and `handback.sh` resumed the lane as attempt 5.

## A/B soak pair: the cut is refuted (Nova, 7f01f7f157, survey route, 300 s)

Read with `docs/lanes/doa413b/ab_read.py <result dir>`. It computes fps as 60 / (the gap between
`[surf413]` lines). The fight window is the lines with 6 active surfaces and under 25 fps.

| arm | request | env | `[lazy413]` at end | fight lines | median fps (min-max) | median `cdef` ms/frame | median frame ms |
|---|---|---|---|---|---|---|---|
| A | `1790473771-doa413b-1386898` | `XEMU_SURF_LAZY_COMPLETE=0` | enabled=0 skips=0 | 46 | **14.9** (4.3-24.4) | 48.4 | 67.1 |
| B | `1790473773-doa413b-1387399` | `=1` | enabled=1 skips=503 reads=0 | 48 | **13.6** (9.6-24.7) | 52.2 | 73.4 |
| pilot | `1790456253-doa413b-520408` | (no lazy code) | | 41 | 12.6 (4.2-23.7) | 54.7 | 79.3 |

B does not beat A. The cause is in B's per-line `lazy` column: all 503 skips fall in a 3-surface
interlude at 20:16:54-20:17:11. There B ran 36-50 fps with `cdef` 0.02 ms, so the path works
where it fires. On every 6-surface fight line `lazy` is 0. So `deferred_downloads_submitted()` is
false at every `surface_update` in the fight, and each one completes the batch as before. The
cut does not reach the wait it was built for. The 1.3 fps gap between A and B is inside the
spread of single runs (the pilot, with no lazy code, read 12.6), so it is not a regression either.

**Default is now OFF** (6cd9507d07): `XEMU_SURF_LAZY_COMPLETE=1` opts in.

## The next lever on #413 (not taken here)

The price stands: in the fight, `Surf` is `cdef`, about 48-55 ms/frame, and `fin` is 0. The probe
cannot tell which of `complete_deferred`'s three branches waits in the fight. Two things fit
`deferred_downloads_submitted()` being false while `cdef` is long:

1. `display_predownload_pending` with `frame_submitted[fi]` false when checked, then true by
   the time `complete_deferred` checks it. That flag is set by the submit worker after
   `vkQueueSubmit` returns, and with the GPU 40-48 ms behind, that submit can block.
2. `deferred_downloads_frame == -1`, a batch recorded into the current command buffer (`dn` is
   ~130 download records per frame in the fight), which goes to `pgraph_vk_finish(SURFACE_DOWN)`.
   `fin`=0 argues against this, unless `fin` misses that caller.

The next lane should count the three branches per 60 frames (display/submitted, coalesced,
finish) and log `frame_submitted[fi]` at the skip check. Then it can decide between (a) a
predicate that treats "enqueued to the submit worker" as submitted, and (b) not recording the
~130 downloads per frame at all. Also, the GPU in this fight is 40-48 ms/frame, so even a full
overlap caps it at about 21-25 fps, not 30.

## Must-not-move arm, re-registered for the default-off build

`docs/testing/predictions/doa413b-defoff-mnm.json`: a_ref a593d8eb85 (master, after the last
merge), b_ref 6cd9507d07. The eight suites of the first arm (`--disc-from` its base request) are
guarded, except `Blend_surface/R5G6B5_Add_SrcA_DstA`. Globs have no exclusion, so the other 31
Blend_surface keys are listed one by one (`register_defoff.py`). A dry judge of a ref-swapped copy
against the first arm's result dirs: `PASS -- all 205 registered checks hold`, so every guard
matches a capture. The arms job runs it from this push. It supersedes the FAIL on the first
file (same issue, newer registration).

## Do not repeat

- Soaks of DOA2U go to the Nova. The Thor has no DOA2U (attempt 3's pair errored at once).
- `LOGCAT_SPEC_OVERRIDE` is the dispatcher's environment, not a request field. Print under `hakuX`.
- Do not "fix" `cdef` by skipping the completion without first logging which branch waits.
  This lane's predicate was false for the whole fight.

## Attempt 5 ends waiting (2026-09-26 ~20:40 PDT)

Waiting on the `[job.arms]` verdict for `doa413b-defoff-mnm.json` (a593d8eb85 vs 6cd9507d07), and
on CI for the pushed head. On PASS: `gh pr ready 440`. Nothing else is left: preflight passes, the
body's `Files:` matches the diff, and the prediction is committed with its refs.

## Why attempt 5 did not finish

It ended correctly, waiting on the default-off arm. That arm was judged PASS (205 checks) at
21:04 PDT, and host ops marked #440 ready. Then lane.local decided (21:14 PDT) that a refuted
cut must not ship as switched-off dead code, and the lane was resumed to strip it.

## Attempt 6: the refuted cut is stripped; what ships is the probe

- Merged origin/master (e5db66fa37). Removed every line of the lazy-completion path from
  vk/surface.c (14ed3ff573): `surf_lazy_complete`, `deferred_downloads_submitted`, the
  display-predownload forget helper, the four `complete_submitted_downloads` call sites, the
  `[lazy413]` log line, the `lazy` column of `[surf413]`, and the tail's two-way branch. The
  surface.c diff against master is now 113 added lines and none removed. All of them are the
  `[surf413]` probe, which compiles to nothing outside `NV2A_PERF_LOG && __ANDROID__` builds.
  `ab_read.py` still reads older soaks' `lazy` column and prints 0 when it is missing.
- dispatcher.sh keeps `xemu-surf:I` in the default logcat spec. It goes live only through the
  host's dispatcher update window after the fold. lane.isoroots now holds dispatcher.sh, and this
  attempt did not edit it.
- Dropped `doa413b-lazy-mnm.json` and `doa413b-defoff-mnm.json`. Both named builds that had the
  lazy path, and nothing else reads them. Registered `doa413b-instr-mnm.json`
  (`register_instr.py`, e5db66fa37 vs 14ed3ff573): the same 8 suites, with the same unguarded
  known-noise row `Blend_surface/R5G6B5_Add_SrcA_DstA`.
- Posted the surface-cost breakdown on #462, which lane.slowdown462 now owns for DOA.
