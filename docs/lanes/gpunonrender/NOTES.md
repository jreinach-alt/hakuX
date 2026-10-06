# gpunonrender (#433): what the non-render GPU time is made of

## Question

belowbar1005 found that on the GPU-bound titles about half of each GPU frame
is not in render passes (`gpu_nonrender_ms`: ToeJam & Earl III 17.9 ms, 007
Agent Under Fire 14.5, DOA Ultimate 13.2, NG Black 11.7, Otogi 11.4, DOA3 10.3,
its dojo stage 25.5; `docs/lanes/belowbar1005/NOTES.md`, "Cross-title"). That
time is not per render pass, and nothing measured what it is inside. This lane
measures it. It changes no behaviour.

## Instrument (commit 16784acb80)

`hw/xbox/nv2a/pgraph/vk/draw.c` holds the bracket and readback code.
`surface.c` and `texture.c` hold the call-site brackets, one per
`pgraph_vk_begin_nondraw_commands()` scope (the only way those functions record
into the frame command buffer). See PR.md for the category table.

- Pool: its own timestamp query pool, created on the first frame when
  `HAKUX_GPUXFR=1`, `2 x 128` queries per frame slot, never destroyed (the
  telemetry runs for the life of the process). `renderer.c` and `renderer.h`
  are not touched.
- Readback: `gpu_xfr_frame()` runs from `gpu_ts_readback()` right after
  `nonrender_ns` is computed, so the residual is against the same number
  `xemu-gpu` reports as Xfr.
- Emission: one window per 60 readbacks (xemu-gpu uses 60 frames of its own
  EMA; these are plain per-frame values, so the statistics are median, mean and
  p90 instead of a smoothed mean).
- Site ids are the source line of the begin call, so a category that holds a
  call site can be traced to its source without a second run.
- Aux-CB brackets are dropped on purpose. `pgraph_vk_begin_single_time_commands`
  (display, renderer init, the `!OPT_SURF_TO_TEX_INLINE` branches) and the
  frame-end staging path (`pgraph_vk_ensure_nondraw_commands`, draw.c) record
  into `aux_command_buffer`, which the timestamps do not cover. Those brackets
  land in `dropped`, so a non-zero `dropped` is the count of work that
  `gpu_nonrender_ms` does not contain.

## Known gaps (not measured by this instrument)

1. **The aux command buffer is outside `gpu_nonrender_ms`.** The frame-end
   `sync_staging_buffer` x3 and `flush_memory_buffer` (vertex, index, uniform
   staging copies) are recorded there, after the main command buffer's end
   stamp. Whether that time is large is not known; `dropped` counts its
   brackets, not its time. Measuring it needs a second pool region with stamps
   in the aux CB, which is a follow-up if the main-CB categories do not account
   for the time.
2. Draws whose bracket would sit inside a render pass are not bracketed (none
   of the categories is in a render pass; the render-pass time is already in
   `gpu_render_ns`).
3. Bytes per operation are not recorded. Ops and ms are.

## Control (done before any title is read)

Two arms, Nova, NG Black, route `belowbar1005/routes/bb-ngb.route` (copied into
the titles routes dir for the request and removed after), perflog build at
16784acb80, `PERF_REGIMEN=default`, 150 s each:

| arm | request | env |
|---|---|---|
| C0 | 1-1791243663-lane.gpunonrender-551868 | `HAKUX_GPUXFR=1` |
| C16 | 1-1791243666-lane.gpunonrender-551969 | `HAKUX_GPUXFR=1 HAKUX_GPUXFR_CTRL=16` |

What "the brackets read a known change" looks like, stated before the runs:

- `ctrl` ms per frame in C16 is the cost of 16 copies. Its per-copy cost is
  that value divided by 16. The size of one copy is not predicted; what is
  predicted is that the value is well above zero and stable across windows
  (p90 close to the median), and that C0 reads no `ctrl` at all.
- `nr` (gpu_nonrender_ms) rises in C16 by about the `ctrl` total. The categories
  other than `ctrl` do not move by more than the spread of the C0 windows
  (median to p90 across windows of C0).
- `res` (residual) does not rise.

What "the brackets do not read it" looks like: `ctrl` reads 0 or is missing
(the stamps are not in the command buffer), or `ctrl` rises but `nr` does not
(the stamps are not where the copies run, or the copies run outside the
measured span), or an unrelated category moves with `ctrl`.

## Attempt 2: why attempt 1 did not finish

Attempt 1 built the instrument, queued the two arms and went WAITING. Both
arms ran to DONE (the apk is fc4e0d3d7a20, built from 16784acb80), but the
attempt stopped there. It never read the `xemu-xfr` lines, and it did not
check that they reached logcat before waiting on them. They did not:

- The dispatcher's logcat spec (`LOGCAT_SPEC` in `docs/testing/dispatcher.sh`,
  ending in `*:S`) is a tag list. `xemu-xfr` is not in it, so every
  `xemu-xfr` line was dropped unread. The C0 logcat has 107 `xemu-gpu` lines
  and no `xemu-xfr` line; the C16 logcat has none either.
- The per-category ms for the control (`ctrl`) therefore does not exist in
  either arm's artifacts.

Fix (attempt 2): the two `xemu-xfr` lines are now logged under the `xemu-gpu`
tag, which is in the spec, with `xemu-xfr` as the message prefix (draw.c,
`xfr_emit`). Adding `xemu-xfr:I` to the spec is the cleaner fix, but the spec
is lane.local's, so it is an OUTBOX request, not a change here.

## Attempt 3: why attempt 2 did not finish

Attempt 2 fixed the tag, queued the two re-run arms and went WAITING. The
re-runs did run to DONE, but the lane was not resumed to read them, so no
`xemu-xfr` verdict was written. One of them (the C0 arm) was voided before any
frame, and attempt 2 did not queue a replacement for it.

## Control verdict (attempt 3)

Four control arms exist, all NG Black on Nova, all at ref 9609d0299f or
16784acb80 as noted:

| arm | request | `xemu-xfr` lines | `xemu-gpu` lines | result |
|---|---|---|---|---|
| attempt 1 C0 | 1-1791243663-lane.gpunonrender-551868 | 0 (tag not in spec) | 107 | ran |
| attempt 1 C16 | 1-1791243666-lane.gpunonrender-551969 | 0 (tag not in spec) | 108 | ran |
| attempt 2 C0 | 1-1791247925-lane.gpunonrender-863985 | 0 | 0 | VOID, see below |
| attempt 2 C16 | 1-1791247926-lane.gpunonrender-864108 | 210 (105 windows) | 313 | ran, read below |

The C16 re-run (864108), per frame, over its 105 `xemu-xfr` windows:

| category | median ms | mean ms | p90 (median of windows) | ops/frame |
|---|---|---|---|---|
| `nr` (gpu_nonrender_ms) | 1.30 | 1.10 | 1.36 | |
| `ctrl` (16 x 1 MiB copies) | 0.68 | 0.68 | 0.68 | 16 |
| `download` | 0.57 | 0.33 | 0.58 | ~2.3 |
| `tex_up` | 0.00 | 0.02 | 0.04 | ~0.1 |
| `surf_up`, `s2t`, `barrier`, `handoff`, `other` | 0.00 | 0.00 | 0.00 | ~1 (barrier) |
| `res` (unbracketed residual) | 0.07 | 0.07 | 0.07 | |

The same run's `xemu-gpu` line: Tot 1.4, Rnd 0.3, Xfr median 1.0 (mean 1.06).
The categories plus the residual reconcile to `nr` within 0.07 ms (under 6%).

Against the criteria written before the readings:

- **`ctrl` reads a known change: PASS.** 0.68 ms per frame, stable (median,
  p90 and max 0.69 across 105 windows), every window counts 16 ops. That is
  0.043 ms per 1 MiB copy.
- **`nr` rises by about the `ctrl` total: PARTIAL.** Only attempt 1 has a C0
  baseline with a usable counter: `Xfr` 0.40 ms (C0) to 1.10 ms (C16), a rise
  of 0.70 ms against `ctrl` 0.68 ms. The attempt-2 C0 is void, so this is one
  pair, not two.
- **Other categories do not move: NOT JUDGED.** No C0 run has a per-category
  reading. Attempt 1's C0 and C16 logs have no `xemu-xfr` lines at all.
- **`res` does not rise: NOT JUDGED** against a baseline, for the same reason.
  The C16 residual is 0.07 ms, which is small.
- **C0 reads no `ctrl`: NOT JUDGED**, same reason.

Verdict: the tag fix works. The instrument reads the known 16-copy cost, and
its categories reconcile with `nr`. The baseline half of the control is not
read yet. The C0 arm that would give it, 863985, was voided before any frame.

The void's cause, from its `run.log`: `FOREGROUND: waiting: foreground-unknown:
ee317437 has no focused window on display 0`, then `ROUTE NOT PLAYED: hakuX did
not hold display 0 and input focus; no input was sent`. This is a
focus-at-start failure, not a performance cause, and it is not known to be
fixed. The first retry is the rule for a single-run flake (the device-run-flakes
note), so the C0 arm was re-queued once at the same ref, route, env and device:

- `1-1791262296-lane.gpunonrender-1610133`: `HAKUX_GPUXFR=1`, NG Black,
  route `gpunonrender-ngb.first-run`, 150 s, perflog, Nova, ref 9609d0299f.

If that run also voids on focus, the next step is a harness question for
lane.local (the focus-at-start path), not another retry of this lane.

Attempt 2's C16 also gives a first look at a category nobody had measured on
menu frames: `download` is 0.57 ms per frame with about 2.3 ops, while
`surf_up` and `s2t` are zero. These are menu frames, so this is not a
gameplay reading. It is the first place the per-category numbers show anything
other than the control.

The branch is 21 commits behind origin/master. It stays at 9609d0299f for the
control, so the control arms match each other. The merge comes before the
title runs.

Spend: not readable from this session, so no figure.

## Attempt 4: why attempt 3 did not finish

Attempt 3 queued the C0 baseline and went WAITING on it, as its own WAITING
file said. The run finished (DONE, 22:49 PDT), but the session that queued it
ended before the result was read, so the baseline was not judged then. The
hostops addendum (22:50 PDT) resumed the lane to do that. Attempt 4 is that
resume. (The brief's header says "attempt 1"; the lane's own count is at 3, and
this section keeps the lane's count.)

## Control verdict (attempt 4): the C0 baseline is read, and the control passes

Pair: C0 `1-1791262296-lane.gpunonrender-1610133` against C16
`1-1791247926-lane.gpunonrender-864108`. Both NG Black on Nova, both apk
`a771c3e50905`, both ref `9609d0299f`, both `PERF_REGIMEN=default`, 150 s, route
`gpunonrender-ngb.first-run`. The only difference is `HAKUX_GPUXFR_CTRL=16`.
The run is menu and cutscene frames only (the route's own frames: publisher
logos, main menu, cutscenes, one black), not gameplay. Clock: GPU 401 MHz,
fixed (`gpu 401-401 of 680`), no thermal pause. Battery 79% at start, on
battery.

C0, per frame, over its 108 `xemu-xfr` windows (`nr` is the lane's
`gpu_nonrender_ms`; the value is the median of the window medians):

| category | median ms | mean ms | p90 (median of windows) |
|---|---|---|---|
| `nr` | 0.62 | 0.37 | 0.67 |
| `ctrl` | 0.00 | 0.00 | 0.00 |
| `download` | 0.56 | 0.28 | 0.58 |
| `tex_up` | 0.04 | 0.02 | 0.04 |
| `surf_up`, `s2t`, `handoff`, `barrier`, `other` | 0.00 | 0.00 | 0.00 |
| `res` | 0.06 | 0.06 | 0.07 |

The same run's `xemu-gpu` per-second line: Tot median 0.7, Rnd median 0.3,
Xfr median 0.40 (mean 0.36). The C0 result has 216 `xemu-xfr` lines and 322
`xemu-gpu` lines; no `xemu-xfr` line is missing from the window count.

Against the criteria written before the readings:

- **C0 reads no `ctrl`: PASS.** `ctrl` is zero in all 108 windows.
- **`nr` rises by about the `ctrl` total: PASS.** C16 `nr` median 1.30 against
  C0 0.62: +0.68 ms, which is the C16 `ctrl` median of 0.68 ms. The `xemu-gpu`
  Xfr medians are 0.40 (C0) and 1.0 (C16, per the attempt-2 read), +0.6; the
  attempt-1 pair gives 0.40 to 1.10, +0.70. Per-second Xfr is a 60-frame smoothed
  value, so it is the coarser of the two readings. The per-frame window medians
  are the reading the control criteria name, and they give +0.68.
- **Other categories do not move: PASS.** `download` 0.56 (C0) against 0.57
  (C16); `tex_up` 0.04 against 0.00, a 0.04 ms difference that is at the level of
  the window spread; `surf_up`, `s2t`, `handoff`, `barrier`, `other` are zero in
  both.
- **`res` does not rise: PASS.** 0.06 (C0) against 0.07 (C16), the window p90
  spread is 0.07 to 0.08 in both.

Verdict: the control passes. The brackets read the known change: 16 copies cost
0.68 ms per frame (0.043 ms per 1 MiB copy), the total moves `nr` by the same
amount, and nothing else moves. The 0.6 ms of `download` in the menu frames is
present in C0 and so is not caused by the control; it is a baseline category of
these frames, which is the first place a non-control category shows a value.

Two limits on this verdict, both stated so the title batch does not inherit
them silently:

1. The control is menu and cutscene frames. It proves the instrument reads a
   known change. It does not say whether the brackets cover gameplay's
   non-render time; that is the title batch's question.
2. The overhead arm (`HAKUX_GPUXFR` unset, same title, same route) is not run.
   The brief requires the bracket's own GPU cost to be measured before the
   title categories are trusted. It goes with the title batch, on the title with
   the most brackets, as the measurement plan says.

No run is pending for the control. WAITING is cleared.

## Attempt 5: why attempt 4 did not finish

Attempt 4 finished what it was resumed for: it judged the C0 baseline, the
control passed, and it ended with nothing queued (WAITING cleared). It did
not start the title batch because the overnight addendum said to stay on the
branch and not merge, and the batch needs origin/master merged first. So the
lane stopped at milestone (a) with no run pending and no next step queued. The
PM addendum of 00:33 PDT 10-06 then added scope (A)-(C) below; this attempt
merged origin/master (4cb9d98c67) and takes it up.

## Scope (A): the Forza `surfupd` round trip, on the GPU (HAKUX_SURFSPLICE)

What frametrace measured (its NOTES, "The PFIFO thread's unhooked wait,
named"): on Forza the PFIFO thread waits 12.2 ms of a 37 ms frame at
draw.c:4319, in non-deferred `SURFACE_DOWN` finishes that
`pgraph_vk_surface_update` submits (surface.c `SDC_SURF_UPDATE`) because a
binding is about to upload from VRAM a pending download is about to write.
lane.forza414 (NOTES 29, 33, 42) already split those finishes: ~1.9 per frame
after hunk 5 (the full-clear share is gone), `why=new` (a fresh zeta binding:
the 640x480 / 1280x480 flips at one address) and `inv`, on draws, so the old
bytes are read and the upload is needed. forza414 42 also found that removing
finishes early in the frame moved most of the wait to the next sync point
(all `[sdcall]` waits fell 1.95 ms of 6.7). So the fix has to remove the round
trip, not move the completion.

The approach (the one that fits a renderer whose surfaces live on the GPU):
both staging buffers already hold guest VRAM bytes. A pending download's
staging rows are exactly what its completion memcpys into VRAM, and an
upload's staging rows are what it memcpys out of VRAM. So the upload reads VRAM
as it is, then the GPU copies every byte a pending download will write over it
from that download's staging rows into the upload's staging, in record order.
That is what VRAM will hold once the downloads complete, and no finish or wait
is needed: the downloads stay pending and complete where any other reader
(range lookup, CPU-access watch, flip, slot rotation) completes them today.
`cpuw0` holds by construction: a guest write over a pending download completes
it first, so at an upload the pending bytes are always newer than VRAM.

Where it does not apply, and what happens instead: a swizzled download (the
CPU swizzles at completion), a batch a finish already submitted (frame >= 0 or
the flip's pre-download), a swizzled upload the CPU unswizzles. These complete
as before, counted as `spl...cmpl`. Commit 5eef1dacd9, surface.c only, behind
`HAKUX_SURFSPLICE=1`, off by default. `[sdcall]` gains
`spl=def<n>/up<n>/dl<n>/<n>kB/cmpl<n>`: updates the switch let defer with an
uploading binding, uploads that spliced, downloads and KiB spliced, uploads
that completed instead. Both perflog and plain builds of surface.c compile
clean with the NDK clang (-Wall, no new warnings).

Not covered: draw.c's own forced completions, texture.c's (`txr dl`, the
`pgraph_vk_flush_all_frames` at the render-to-texture bind, forza414 28), and
surface.c:1266's fence wait (3.1 ms on Forza). If the wait moves there, that is
the reading, not a failure of the splice.

### Runs and their expected results (written before queueing)

All on the Nova, perflog, ref 5eef1dacd9, `PERF_REGIMEN=default`,
`HAKUX_GPUXFR=1` in every arm (the same instrument on both sides of the A/B).

| arm | title, route, s | extra env |
|---|---|---|
| F0 | Forza, `forza.drive`, 300 | none |
| F1 | Forza, `forza.drive`, 300 | `HAKUX_SURFSPLICE=1` |
| S0 | Spider-Man 2, `gnr-spiderman2` (this dir), 300 | none |
| M0 | Midnight Club II, `gnr-mc2` (this dir), 330 | none |

Forza window: the race, from the route's `mark gameplay` to the end; per-frame
values are `[sdcall]` sums over the window divided by its frames.

- **Mechanism (F1):** the log has `[surfsplice] on`; `spl=up` > 0 and `spl=dl`
  > 0 per window; F0 has `spl=` all zero. If F1 shows `spl=up0`, the switch did
  not reach the app or nothing was spliceable: no further reading.
- **P1, the finish is gone:** F1 `surfupd` fin per frame <= 30% of F0's.
- **P2, the wait left the thread (the claim):** the sum of all `[sdcall]`
  completion waits per frame (every caller) in F1 <= 60% of F0's, and the
  `hakuX-stall` `Fin` per frame falls by at least half the F0 `surfupd` wait.
  If P1 holds and P2 fails, the wait moved to the next sync point (forza414
  42's shape): the splice is correct and is not the fps lever, and the caller
  the wait moved to is the next target.
- **P3, safety:** no crash or hang line; the route frames of F1 show the same
  scenes as F0 with no depth or colour corruption (the splice is a byte copy;
  a wrong offset shows as torn or banded geometry).
- **Readout, not a leg:** fps in the race window. Forza needs 3.6 ms a frame
  for its 30; if P2 holds at full size (12 ms) Forza holds 30.

Scope (B), S0 and M0 (and F0): the `xemu-xfr` category table per title, and
the `[sdcall]` line. The question is whether (A) reaches them:

- **(A) reaches the title:** `[sdcall]` `surfupd` wait >= 3 ms/frame with
  `su_upl` >= 0.5/frame, `why=` mostly `new`/`inv`/`stale` (bytes a download
  is about to write). Then a splice arm on that title is the next run.
- **It does not:** `surfupd` wait < 1 ms/frame, or the wait sits in another
  caller (`tobuf`, `range`, `txr`). Then the title's missing time is elsewhere,
  named by the caller that carries it.
- The GPU categories (`download`, `surf_up`) show the copies' GPU time, not the
  PFIFO's wait for the fence. A round trip costs mostly the wait, so the
  categories can be small while the round trip is the cost. Both are recorded;
  the `[sdcall]` wait is the one that answers (B).

Scope (C) (Simpsons, pfifo.lock across the STALLED finish's slot-fence wait)
needs reports.c and pfifo.c, held by lane.accuracy804 and lane.vcpusleep. It
waits on those rows; asked in OUTBOX.

## Attempt 6: why attempt 5 did not finish

Attempt 5 did not fail. It built (A), wrote the expected results, queued F0, F1,
S0 and M0, set WAITING on them and ended. That is a finished wait. All four
ran DONE on the Nova between 03:00 and 03:53 PDT on 10-06. This attempt reads
them.

## The four runs read (attempt 6)

Reader: `abread.py <id> --from HH:MM:SS` (new). It gives per-frame sums of
`[sdcall]`, `hakuX-stall` finishes, gfps, `xemu-gpu` and `xemu-xfr` over the
window. Windows run to the end of the log. Forza starts 20 s after the drive
reached play (F0 03:02:37, F1 03:26:36). S0 and M0 start at `mark gameplay`
+ 20 s (03:43:38 and 03:50:25).

- All four ran at GPU 401 MHz for the whole run (run.log THERMAL `gpu 401-401
  of 680`). There was no thermal pause. The device was on USB (6.5 W in), with
  the battery at 79% at the start.
- The A/B pair is compared at that one clock. The clock is a fact of these
  runs, not a lever. Under the energy rule, nothing here asks for a faster one.

### `xemu-xfr` is per command buffer; `xemu-gpu` is per guest frame

`xemu-xfr` takes one sample per readback, which is one per command buffer.
`xemu-gpu` sums a guest frame. Command buffers per frame (readbacks / frames)
link the two, and the scaled `nr` matches `Xfr` in all four runs:

| run | CB per frame | `nr` per CB | x CB = per frame | `xemu-gpu` Xfr |
|---|---|---|---|---|
| F0 | 7.19 | 0.44 | 3.13 | 3.01 |
| F1 | 5.61 | 0.68 | 3.79 | 3.73 |
| S0 | 10.00 | 0.78 | 7.78 | 8.01 |
| M0 | 4.01 | 0.19 | 0.77 | 0.78 |

The control verdict still stands: it compared `ctrl` with `nr`, and both are
per CB. `abread.py` prints the per-frame values.

### Scope (A), Forza F0/F1: the splice works, and the wait moves to the texture scan

| per frame | F0 (splice off) | F1 (`HAKUX_SURFSPLICE=1`) |
|---|---|---|
| gfps (mean) | 22.1 | 19.9 |
| `[sdcall]` surfupd: fin, wait ms | 2.00, 9.64 | 0.00 (0.25 fence), 0.24 |
| `[sdcall]` range: fin, wait ms | 0.97, 8.10 | 1.95, **19.29** |
| `[sdcall]` record: wait ms | 6.34 | 5.49 |
| `[sdcall]` all callers, wait ms | **24.13** | **26.30** |
| `spl` up / dl / KiB | 0 / 0 / 0 | 2.00 / 2.00 / 300 |
| `su_upl`, `why` | 2.00, all `inv` | 2.01, all `inv` |
| finishes (`sd`) | 4.21 (3.01) | 3.50 (2.26) |
| texture bind surface scan (`txw scan`, texture.c:2100) ms | 8.16 | **19.35** |
| `xemu-gpu` Tot / Rnd / Xfr | 37.8 / 34.8 / 3.0 | 43.7 / 40.0 / 3.7 |

Against the expected results:

- **Mechanism: holds.** F1 logs `[surfsplice] on` and splices 2.00 uploads
  and 2.00 downloads per frame (300 KiB). F0 splices none.
- **P1: holds.** `surfupd` finishes go from 2.00 to 0.00 per frame.
- **P2: fails.** The all-caller wait is 109% of F0's (the bar was 60% or less).
  Finishes fall by 0.71 per frame, which is less than the 1.0 the leg needed.
  The wait moved to `range` (`pgraph_vk_download_surfaces_in_range_if_dirty`,
  surface.c:739). Its finishes double and its wait rises 11.2 ms. The texture
  bind's surface scan (texture.c:2100, `TXW_BEGIN(SCAN)`) rises by the same
  11.2 ms. This is forza414 42's shape.
- What it means: the bytes that the splice left pending are read by a texture
  bind through VRAM, so that reader completes them. The upload was never the
  only consumer of the download. On Forza the round trip belongs to a texture
  that samples a rendered surface's VRAM.
- **P3:** there is no crash or hang line. The drive route takes no frames, so
  corruption is not judged. The splice stays default off.
- **Readout:** gfps fell 22.1 to 19.9, but Rnd (render-pass time, which the
  splice does not touch) rose 34.8 to 40.0. The two races differ in scene, and
  the fps difference is not attributed to the splice.
- `why` is `inv` here, not the `new`/`stale` mix that forza414 read at an
  older ref.

Verdict: (A) is correct but is not Forza's fps lever. The next target on Forza
is texture.c:2100: a texture bind whose range overlaps a pending download
completes it, because the texture is read from VRAM rather than from the
surface's image.

### Scope (B), S0 Spider-Man 2 and M0 Midnight Club II

| per frame | S0 Spider-Man 2 | M0 Midnight Club II |
|---|---|---|
| gfps (mean) | 26.8 | 23.7 |
| `[sdcall]` surfupd: fin, wait ms | **2.50, 6.01** (`su_upl` 2.50, all `stale`) | none |
| `[sdcall]` range: fin, wait ms | 1.00, 0.56 | 1.00, **7.98** (dl 2.5) |
| `[sdcall]` record: wait ms | 4.35 | 0.01 |
| `[sdcall]` all callers, wait ms | 10.91 | 8.00 |
| finishes (`sd`) | 5.50 (4.50) | 2.61 (1.51) |
| `xemu-gpu` Tot / Rnd / Xfr | 19.8 / 11.8 / 8.0 | 34.6 / 33.8 / 0.8 |

- **Spider-Man 2: (A) reaches it** by the stated rule: a `surfupd` wait of
  6.0 ms (at least 3), `su_upl` 2.5 (at least 0.5), all `stale`. A splice arm
  is the next run (S1 below). F1 already showed a splice can move the wait
  instead of removing it. On S0 the texture scan's `range` wait is 0.56 ms, so
  whether the same thing happens is open.
- **Midnight Club II: (A) does not reach it.** It has no `surfupd` wait. Its
  8.0 ms is in `range`, the caller that Forza's wait moved to.
- So (A) can clear at most one more title (Spider-Man 2). `range` carries the
  wait on two titles (M0, and F1 once the splice removes `surfupd`). That
  makes texture.c:2100's scan the common target.

### The GPU categories, per frame, and the residual

| per frame, ms (share of `nr`) | F0 | F1 | S0 | M0 |
|---|---|---|---|---|
| `nr` | 3.13 | 3.79 | 7.78 | 0.77 |
| download | 1.53 (49%) | 1.61 (43%) | 0.60 (8%) | 0.40 (52%) |
| s2t | 0.40 (13%) | 0.39 (10%) | 0.19 (2%) | 0 |
| surf_up | 0.07 | 0.34 | 0.50 (6%) | 0 |
| tex_up | 0.05 | 0.06 | 0.10 | 0 |
| **res (unbracketed)** | 1.07 (34%) | 1.37 (36%) | **6.48 (83%)** | 0.36 (47%) |

The residual is above 15% in all four runs. By the decision rules, these
category tables are not complete. On Spider-Man 2, 83% of `gpu_nonrender_ms`
is outside every bracket. The next section names what that is.

## What `gpu_nonrender_ms` is on Turnip: render-pass work behind a stamp placement

The render-pass stamps (`begin_render_pass` / `end_render_pass`, draw.c) are
written **inside** the render pass. Turnip (tu_query_pool.cc:2108-2112, the
fork's Mesa tree at `/home/justin/hakux-work/mesa-turnipfork`) says:

> Inside a render pass, just write the timestamp multiple times so that the
> user gets the last one if we use GMEM.

The stamp goes into the pass's `draw_cs`. A GMEM pass replays that stream
once per tile (bin), after a binning pass, with tile loads and stores around
each replay. So in a GMEM pass, Rnd is **the last tile's draws only**.
`gpu_nonrender_ms` = CB span − Rnd then holds the binning pass, every other
tile's draws, and every tile load and store. A sysmem pass (which Turnip's
autotune picks per pass) is stamped correctly.

That fits what was measured:

- **belowbar1005's Xfr/Tot sits at 0.49-0.56** on NG Black, AUF, Otogi, DOA3
  and Black. That is what two bins per pass give when the stamp sees one of
  them.
- It does not track the pass count. The bin count depends on resolution and
  attachment format, not on the number of passes. Otogi's 2 large passes give
  11.4 ms; Top Spin's 149 small passes are probably mostly sysmem.
- Forza (Rnd 35 of Tot 38) and Midnight Club II (34 of 35) read as almost all
  render. That is the sysmem pattern, and their residuals are small in ms.
  Spider-Man 2 reads as half non-render with 83% unbracketed.
- `TU_DEBUG=sysmem` gained 8 gfps on DOA and AUF (lane.flip474), the two
  titles with the most "non-render" time after ToeJam.

So belowbar1005's premise, "half of every GPU frame is not render passes", is
very likely an artifact of where the stamps sit. In that case the half is
render-pass work (tiles, binning, loads and stores), and no copy or upload
category will account for it. That is a hypothesis with code-level evidence,
not yet a measurement. X0 below measures it.

**The in-pass stamps also cost GPU time, in every build.** `gpu_ts_supported`
is set whenever the device has timestamps (renderer.c:490-506), with no
`NV2A_PERF_LOG` guard. The only readers are telemetry (`g_nv2a_stats`
phase stats and frametrace's `gpu_ns`). The end stamp is BOTTOM_OF_PIPE, and
for that Turnip emits a wait-for-idle before the counter read
(`emit_counter_barrier`, tu_query_pool.cc:2122-2132). Inside `draw_cs`, that
is **one wait-for-idle per tile per render pass**, plus one in the binning
pass, in the shipped build. X1 below measures what it costs.

### The instrument (this commit, draw.c only; defaults unchanged)

- With `HAKUX_GPUXFR=1`, every render pass also gets a stamp pair **outside**
  it. The begin stamp (TOP_OF_PIPE) is written before `vkCmdBeginRenderPass`
  and the end stamp (BOTTOM_OF_PIPE) after `vkCmdEndRenderPass`. Up to 64 per
  CB, in the xfr pool. Turnip emits a GMEM pass's binning, tiles, loads and
  stores at `vkCmdEndRenderPass`, between these two stamps.
- A new line, `xemu-xfr XFR rp in/out/nr_out/res_out <med mean p90> n<rp per
  CB> inrp<0|1> dropped`, gives, per CB:
  - `in`: the render span from the in-pass stamps (Rnd).
  - `out`: the render span from the outer stamps.
  - `nr_out`: CB span − `out`.
  - `res_out`: `nr_out` − the bracketed categories.
- `HAKUX_GPUTS_INRP=0` leaves out the in-pass pair (Rnd then reads 0). It is
  read once and cached, and has no effect when unset.
- Overlap caveat: a TOP_OF_PIPE begin stamp can fire while unbracketed work
  recorded just before the pass is still running. That is counted on the
  render side. Bracketed work ends in a BOTTOM_OF_PIPE stamp, so it is drained
  first.
- The outer end stamp adds one wait-for-idle per pass in xfr-on arms only
  (not one per tile).
- The NDK clang build is clean (perflog and release, `-Wall`, no new
  warnings).

### Runs and their expected results (written before queueing)

All on the Nova, perflog, `PERF_REGIMEN=default`. Window: `mark gameplay` +
20 s to the end.

| arm | title, route, s | ref | env |
|---|---|---|---|
| X0 | NG Black, `belowbar1005/routes/bb-ngb` (belowbar's own run), 480 | this commit | `HAKUX_GPUXFR=1` |
| X1 | the same | this commit | `HAKUX_GPUXFR=1 HAKUX_GPUTS_INRP=0` |
| S1 | Spider-Man 2, `gnr-spiderman2`, 300 | 5eef1dacd9 (S0's apk) | `HAKUX_GPUXFR=1 HAKUX_SURFSPLICE=1` |

**X0: is the "non-render" time render-pass work behind the stamps?**
belowbar read NG Black at Tot 23.9 = Rnd 12.2 + Xfr 11.7.

- **The stamps hide it (expected):** per frame, `out` − `in` is at least 50%
  of `nr`, and `nr_out` is at most 50% of `nr`. Then belowbar's survey and this
  lane's question rest on a stamp artifact. The GPU's real non-render time is
  `nr_out`, and its share is what any fix of copies or uploads could win.
- **It is real between-pass work:** `nr_out` is at least 80% of `nr`. Then the
  outer stamps barely move it, and `res_out` names how much is outside the
  brackets (the aux CB, barriers).
- In between: both effects are present, and the numbers give each one's size.

**X1: what the in-pass stamp pair costs the GPU.** Compared with X0 per frame
on `out` (render span) and `xemu-gpu` Tot:

- **They cost:** X1's `out` per render pass is at most 0.9 x X0's, and Tot per
  frame falls by at least 1 ms. Then a fix lane removes them from the release
  build: either gate them on `NV2A_PERF_LOG`, or move them outside the pass.
- **Nothing measurable:** per-pass `out` is within ±10% of X0's. Scene
  differences between two route runs are about that size, so this arm cannot
  see a smaller cost.
- gfps is a readout, not a leg.

**S1: does the splice remove Spider-Man 2's wait, or move it?** These are
F1's legs against S0:

- Mechanism: `spl` up > 0.
- P1: `surfupd` finishes are at most 30% of S0's 2.50.
- P2: the all-caller wait is at most 60% of S0's 10.91 (6.5 ms or less), and
  finishes fall by at least 1.25 per frame.
- If P1 holds and P2 fails, the wait moved (name the caller, as on Forza).
- Readout: gfps (S0 26.8; 30 needs 3.3 ms off the period).

## Scope (C), Simpsons: the measured outcome of the lock half already exists

The PM's (C) is to release pfifo.lock across the STALLED finish's slot-fence
wait (draw.c's rotation `vkWaitForFences`, frametrace's 4386, now ~4804).
For the vCPU, that has the same effect as vcpusleep's posted DMA_PUT store
(c2dfca18a1): the guest's DMA_PUT no longer waits for the PFIFO thread's
fence wait. That change ran on Simpsons (simp2), and it was reverted in
f6ac723228 for this reason:

> the vCPU's off-CPU time fell from 19,987 to 2,543 ms a minute and v_blk from
> 8.85 to 0.80 ms/frame, but fps went from 40.0 to 36.2-37.9. The freed time
> became guest idle that the vCPU spins through, and the PFIFO thread's
> frame-slot fence wait grew from about 8 to 21 ms a frame.

So the lock is not what paces Simpsons. The rotation fence wait is.
- There are ~8.8 STALLED finishes a guest frame, and each one rotates one of 3
  slots and waits for the command buffer two finishes back. The GPU is busy
  24% of the frame (frametrace: 5.9 ms at 615 MHz).
- That is submit-to-completion latency, paid ~9 times a frame, not GPU
  throughput.
- Freed from the lock, the guest pushes faster, and the PFIFO thread waits
  more often. That is simp2's 8 to 21 ms.

Releasing the lock as briefed is expected to reproduce simp2. I put its P at
0.1 (it removes the same vCPU wait simp2 removed) and did not build it.

### (C'): no STALLED submit unless a report is queued (HAKUX_STALLFIN=reports)

What a STALLED submit gives the guest:
- Semaphore releases are written at the method (pgraph.c:5275-5294).
- Surface bytes the CPU reads are downloaded by their own finishes.
- The zpass reports are the only guest-visible value written after a finish
  (`pgraph_vk_process_pending_reports_internal`).

The STALLED finish is upstream's "Finish when queue is empty" (c41853a3f3).
hakuX made it deferred (2b33fd95e7) and batched (f534b0bb51). With
`HAKUX_STALLFIN=reports`, a caught-up FIFO submits only when `report_queue`
is non-empty. Otherwise the draws stay in the command buffer until the flip or
another finish submits them, which removes the rotation, and so its fence
wait, at every other catch-up.
- Change: `vk/reports.c` only (granted 03:33). The flag is read once, logs
  `[stallfin] reports-only on` (hakuX-vk), and is off by default.
- NDK clang: clean for perflog and release.
- What it gives up: the GPU starts a frame's draws at the flip rather than at
  each catch-up. That costs throughput only if the GPU would otherwise sit
  idle with work queued. With 3 slots the PFIFO thread still runs up to two
  submits ahead.
- Risk to check: a guest that waits on a GPU product other than a report with
  the FIFO idle. None is known in the code (the list above). A hang would show
  in the run as a frozen route frame or a missing flip.

Runs (expected results written before queueing). Both arms: the Nova,
perflog, `PERF_REGIMEN=default`, this commit, Simpsons
`frametrace/simpsons-frametrace` route, 420 s. Window: `mark gameplay` + 20 s
to the end. Frames every 20 s. K0 has no env; K1 sets `HAKUX_STALLFIN=reports`.

- **Mechanism:** K1 logs `[stallfin] reports-only on`. Its STALLED finishes
  (`stl` + `stlDef` in `hakuX-stall Finish`) per frame are at most 30% of
  K0's. If not, Simpsons' STALLED finishes carry reports, and this gate cannot
  reach them.
- **The wait leaves the chain (the claim):** K1's `[rwait526]` rotate waits
  and the finish count per frame fall, and gfps rises by at least 5 (40.9 in
  frametrace's window, not this route's K0). Use K0 as the baseline.
- If finishes fall and fps does not rise, the pacer moved. The next reading
  is where the PFIFO or the guest waits in K1 (`lockw`, `hakuX-stall`
  finishes by reason).
- **Safety:** the route reaches free roam in both arms (frames). No crash or
  hang line. K1's frames are free of missing geometry. A report-dependent
  effect would show as a flicker or missing pass. The owner checks flicker,
  so this arm's frames are evidence, not a sign-off.
- Readout: fps period p50, and finishes per frame by reason.

## Attempt 7: why attempt 6 did not finish

Attempt 6 did not fail. It built the outer stamps (d946e1ba44) and
`HAKUX_STALLFIN=reports` (6f6af20088), wrote the expected results, queued five
Nova runs, set WAITING on them and ended. That is a finished wait. All five ran
DONE on the Nova between 04:12 and 04:50 PDT on 10-06. This attempt reads them.
`origin/master` had not moved since the last merge (0 commits), so there was
nothing to merge.

## The five runs read (attempt 7)

Reader: `abread.py <id> --from <mark gameplay + 20 s>`, to the end of the log.
Device state (run.log THERMAL, thermal.jsonl): no thermal pause in any run; on
USB (5.2-6.5 W in) with the battery at 80% at the start.

| run | id | GPU MHz in the window |
|---|---|---|
| X0 | 1-1791284834-lane.gpunonrender-3228352 | 680 (one 550 sample) |
| X1 | 1-1791284845-lane.gpunonrender-3230278 | 680 (one 550 sample, same place) |
| S1 | 1-1791284850-lane.gpunonrender-3230633 | 401 |
| K0 | 1-1791285173-lane.gpunonrender-3251320 | 401 |
| K1 | 1-1791285177-lane.gpunonrender-3251434 | 401 (one 475 sample) |

Each pair ran at the same clock, so no clock state is read as a cost.

### X0: the "non-render" half is render-pass work behind the in-pass stamps

NG Black, `bb-ngb`, window 04:18:02-04:21:07 (185 s of play), per frame:

| quantity | ms/frame | share of `nr` |
|---|---|---|
| `xemu-gpu` Tot / Rnd / Xfr | 22.96 / 12.07 / 10.89 | |
| `nr` (CB span − in-pass render spans, from `xemu-xfr`) | 10.75 | 100% |
| `in`: render span, in-pass stamps | 11.91 | |
| `out`: render span, outer stamps | 22.27 | |
| **`out` − `in`: render-pass work the in-pass stamps miss** | **10.36** | **96%** |
| **`nr_out`: CB span − outer render spans** | **0.39** | **3.6%** |
| download (6.14 ops/frame, site 587) | 0.35 | |
| s2t (0.68 ops/frame) | 0.01 | |
| `res_out` (outside every bracket, outside every pass) | 0.02 | |

Render passes: 11.96 per frame, so the in-pass stamps miss 0.87 ms per pass.

Against the rule written before the run: **"the stamps hide it" holds**, far
past its bar. `out` − `in` is 96% of `nr` (the bar was at least 50%), and
`nr_out` is 3.6% of `nr` (the bar was at most 50%).

- On NG Black, the GPU's real time outside render passes is **0.39 ms a frame**,
  not 10.9. It is 1.7% of the GPU frame.
- The categories reconcile under the outer stamps: download 0.35 + s2t 0.01 +
  `res_out` 0.02 = 0.38 of `nr_out` 0.39. The unbracketed residual is 5% of
  `nr_out`, under the 15% bar, so this title's table is complete.
- The largest category is `download` at 90% of `nr_out`. At 0.35 ms a frame it
  cannot move fps: the most it can win is 0.35 of a 26.8 ms G frame.
- The other 10.4 ms that belowbar1005 read as non-render is the work Turnip
  emits at `vkCmdEndRenderPass` for a GMEM pass: the binning pass, every tile
  but the last, and the tile loads and stores (tu_query_pool.cc:2108; the
  section above). The GPU frame on NG Black is 97% render passes.

So the brief's premise, "half of every GPU frame is not render passes", is a
stamp artifact on NG Black, measured. No copy, upload or conversion fix can win
the 10-18 ms the survey promised there. The GPU's time is inside the render
passes, and the lever is how each pass runs on a tiler: GMEM vs sysmem, bin
count, and which attachments are loaded and stored per tile.

### X1: the in-pass stamp pair costs nothing measurable

| per frame | X0 (in-pass on) | X1 (`HAKUX_GPUTS_INRP=0`) |
|---|---|---|
| render passes | 11.96 | 11.98 |
| `out` render span | 22.27 | 22.42 |
| `out` per pass | 1.862 | 1.871 |
| `xemu-gpu` Tot | 22.96 | 23.20 |
| `nr_out` | 0.39 | 0.39 |
| gfps (readout) | 39.2 | 38.3 |

Per-pass `out` is +0.5% with the stamps removed (the bar for "they cost" was
at most 0.9×), and Tot did not fall. Verdict: **nothing measurable**. A
wait-for-idle per tile per pass is below this arm's ±10% resolution on NG Black.
The shipped build keeps the stamps, and this is not a fix candidate.

### S1: the splice never engaged on Spider-Man 2

| per frame | S0 (splice off) | S1 (`HAKUX_SURFSPLICE=1`) |
|---|---|---|
| `[surfsplice] on` logged | no | yes (04:30:14) |
| `spl` def / up / dl / cmpl | 0 / 0 / 0 / 0 | **0 / 0 / 0 / 0** |
| `[sdcall]` surfupd: fin, wait ms | 2.50, 6.01 | 2.50, 6.29 |
| all callers, wait ms | 10.91 | 11.55 |
| `su_upl`, `why` | 2.50, all `stale` | 2.50, all `stale` |
| gfps | 26.8 | 26.5 |

The mechanism leg fails. `spl def` counts updates that the switch let defer
with a binding uploading, and it is 0. So `surface_update_may_defer_downloads`
refused every one: `surfsplice_covers` was false for a binding each time. That
happens when an overlapping pending download is swizzled, has a host format
whose bytes per pixel differ from the guest's, or is already submitted (it is
not: the `surfupd` waits are finishes, not fence waits), or when the uploading
binding is swizzled and not 4 bytes per pixel. Which one applies is not
counted. P1 and P2 are not judged, because nothing was spliced. The run is not
void: the build, env and route are correct, and the gate itself is what the
run measured.

Verdict: (A) does not reach Spider-Man 2 as built. Reaching it would need a
refusal-reason counter, then (if the download is swizzled) a GPU swizzle in
the splice, then a run. F1 already showed the wait can move to another caller
once `surfupd` is removed. Ranked below (P 0.15).

### K0/K1: STALLED submits fall to 20%, and fps falls

Simpsons, `simpsons-frametrace`, both in free roam at the same wall (frames
f00012 of each: Homer, the brick wall, the window; FPS overlay 34 in K0, 25 in
K1). No crash or hang line. K1's frames show no missing geometry (the flicker
check is the owner's).

| per frame (window means) | K0 | K1 (`HAKUX_STALLFIN=reports`) |
|---|---|---|
| `[stallfin] reports-only on` | no | yes |
| STALLED finishes (`stl`), `stlDef` | 5.36, 5.36 | **1.05**, 2.05 |
| all finishes | 6.37 | 2.35 (adds `pres` 0.30) |
| `[rwait526]` deferred waits per 10 s, wait ms | 1617, 112 | 539, 47 |
| **gfps** | **30.3** | **25.8** |
| G (guest frame ms) | 33.0 | 37.75 |
| vCPU DMA_PUT wait on pfifo.lock (`CPU: Lw`) | 16.1 | **20.4** |
| `[lock474]` flip op holding pgraph.lock, ms per 2 s | 0.4 | 17.7 |
| `[lock474]` vCPU register-read wait, ms per 2 s | 0.7 | 10.2 |
| fifoskew drain mean, ms | 3.90 | 4.19 |
| `xemu-gpu` Tot / Rnd / Xfr | 19.6 / 12.6 / 7.0 | **25.7** / 12.7 / **13.0** |

Against the rules written before the runs:

- **Mechanism: holds.** STALLED finishes are 20% of K0's, under the 30% bar.
  Simpsons' catch-ups do not carry reports.
- **The claim: fails.** gfps fell by 4.5 (it needed to rise by at least 5).
  The rotation wait fell, but it was small on this route. K0's deferred
  rotation wait is 112 ms per 10 s, about 0.37 ms a frame, not the 8 ms that
  simp2 measured in frametrace's window. K0 runs at 30 fps here, not 40.9, so
  this route's scene is paced by something else.
- **The pacer moved, and is named by the counters:**
  - The vCPU's DMA_PUT wait on pfifo.lock grew by 4.3 ms a frame. That is
    about the 4.75 ms the guest frame grew.
  - The GPU frame grew 6.1 ms at the same 401 MHz, and all of it is outside
    the in-pass stamps (Rnd unchanged). After X0, that is most likely
    render-pass work (bins and tiles), not copies. Batching more draws into
    one submit made the GPU's frame longer. Why is not measured.
  - The flip now holds pgraph.lock for 0.33 ms a flip (was 0.01). That is
    small per frame, but it is the place where a whole frame's work is now
    submitted.
- Reading: with catch-up submits gone, the GPU starts a frame's work at the
  flip, and the PFIFO thread (holding pfifo.lock, which the vCPU's DMA_PUT
  waits for) waits for that work behind it. The overlap the per-catch-up
  submits gave between recording and GPU execution was worth more than the
  rotation waits they cost.

Verdict: (C') is refuted on Simpsons and stays default off. Together with
simp2 (the lock half, refuted in f6ac723228), both halves of (C) have been
tried and both lost fps. Neither the STALLED submit nor the lock across its
wait is what holds Simpsons at 30-40 fps on these routes.

### Next runs: is the stamp artifact the same on the other titles?

X0 settles NG Black. The brief asks for six titles, and the decision that
depends on them is whether any title has real between-pass GPU work worth a
fix lane. Two titles can be run on the Nova now with existing routes. **ToeJam
& Earl III** has the largest `nr` (17.9 ms) and the lowest Xfr/Tot (0.34), so it
is the one most likely to differ from NG Black. **DOA3** has the dojo stage
(25.5 ms `nr`). Otogi's route and title are on the Thor, which is out of
service (fan). AUF and DOA Ultimate have no route.

Both runs: Nova, perflog, `PERF_REGIMEN=default`, `HAKUX_GPUXFR=1`, ref
d946e1ba44 (X0's apk, so the shader cache carries over only if no other apk
ran between). Window: `mark gameplay` + 20 s to the end.

| arm | title, route, s |
|---|---|
| T0 | ToeJam & Earl III, `uberdefault569/routes/toejam-earl-3`, 300 |
| D0 | DOA3, `belowbar1005/routes/bb-doa3`, 480 (attract reaches the dojo at about 270-330 s) |

Expected results, per title, written before queueing:

- **The artifact holds there too:** `nr_out` is at most 30% of `nr`. Then the
  survey's non-render time is render-pass work on that title as well.
- **Real between-pass work:** `nr_out` is at least 80% of `nr`, with `res_out`
  at most 15% of `nr_out`. Then that title's largest category is ranked as
  the brief asks (avoidable or inherent, from the code path).
- In between: both are present, and the numbers give each one's size.
- The brief's "this category is the cost" rule (one category at least 50% of
  `nr` in at least 3 of 6 titles) is judged on `nr_out` for every title with
  outer stamps. NG Black counts as "not": its largest category is 3.3% of
  `nr`.

## Attempt 8: why attempt 7 did not finish

Attempt 7 did not fail. It read X0/X1/S1/K0/K1, queued T0 and D0, set WAITING
on them and ended. That is a finished wait. T0 ran 05:01-05:07 PDT and D0
05:07-05:16 PDT, both DONE, and hostops' restore
(1791288512-hostops-restore-c3a0b, master, empty env) ran DONE after D0, so the
Nova is off the lane build. origin/master had not moved (0 commits to merge).

## T0 and D0 read (attempt 8)

Reader: `abread.py <id> --from <mark gameplay + 20 s>`. Both runs at
d946e1ba44, `HAKUX_GPUXFR=1`, `PERF_REGIMEN=default`, no thermal pause,
battery 80% (on USB, 6.0-6.1 W in; it read "Charging" for part of each run).

| run | id | window | GPU MHz (thermal.jsonl) |
|---|---|---|---|
| T0 ToeJam & Earl III | 1-1791288045-lane.gpunonrender-3440051 | 05:04:18-05:07:01 (163 s) | 401, every sample |
| D0 DOA3 | 1-1791288049-lane.gpunonrender-3440825 | 05:10:51-05:15:48 (297 s) | 680 to 05:13:17, then 401 |

What was on screen (route frames): T0 is the in-game "Vinyl Albums" overlay
drawn over the live 3D world for the whole window (the route's inputs opened
it; 23-30 fps on the overlay counter). That is the same route uberdefault569 and
belowbar1005 used, and `Xfr` median reads 17.9 ms, the survey's own figure, so
it is the survey's workload. It is not free-roam play. D0 is a fight in the cage
stage ("YOU LOSE" at 05:11:45) while the clock is 680, then the attract title
screen at 401. The dojo stage was not on screen in this window, so D0 is split
by clock and scene below.

Per frame (window sums over `[sdcall]` frames; `xemu-xfr` per CB times CBs per
frame):

| quantity | T0 ToeJam | D0 fight (680 MHz) | D0 title (401 MHz) |
|---|---|---|---|
| gfps mean | 25.4 | 36.6 | 48.5 |
| `nr` (in-pass stamps) | 17.45 | 13.32 | 9.42 |
| `in` render span | 31.05 | 13.36 | 11.46 |
| `out` render span | 47.95 | 26.41 | 20.55 |
| **`out` − `in`, share of `nr`** | **16.90, 97%** | **13.05, 98%** | **9.09, 96%** |
| **`nr_out`, share of `nr`** | **0.55, 3.2%** | **0.26, 2.0%** | **0.34, 3.6%** |
| largest category: `download` | 0.46 (site 587 0.44) | 0.24 | 0.30 |
| `res_out` (outside every bracket and pass), share of `nr_out` | 0.09, 16% | 0.01, 4% | 0.03, 9% |
| render passes | 17.6 (9.3 counted once, T1) | 2.1 | 4.7 |

T0's absolute ms and pass count are over-counted by its one `sd` finish a frame
(the next section; T1 below has the values counted once). Its shares are not.

Against the rule written before the runs: **the artifact holds on both titles,
far past its bar** (`nr_out` at most 30% of `nr`; it is 2-4%). On ToeJam, the
title with the largest survey `nr` and the lowest Xfr/Tot, 97% of its "non-render"
time is render-pass work the in-pass stamps miss.

- The real between-pass GPU time is 0.26-0.55 ms a frame on all three readings,
  and its largest category is `download` (site 587) every time.
- T0's `res_out` is 16% of `nr_out`, just over the 15% bar, but it is 0.09 ms a
  frame (0.2% of the GPU frame). What is outside the brackets there is not
  named; at that size it cannot move a ranking.
- The brief's decision rule ("this category is the cost": one category at least
  50% of `nr` in at least 3 of 6 titles) is judged **not**: NG Black, ToeJam and
  DOA3 each put their largest category at 2-3% of `nr`. Otogi (Thor, out of
  service), AUF and DOA Ultimate (no route) were not run. The rule could only
  flip if all three of them showed at least 50% real between-pass work, against
  a driver mechanism (Turnip's last-tile stamp, tu_query_pool.cc:2108) that
  applies to every GMEM pass and gave 96-98% on all three measured titles. No
  run is queued for them.

### The GPU timestamps count some command buffers twice

T0's per-frame GPU span (Tot 48.5 ms) is longer than its frame (38.4 ms at the
`[sdcall]` frame rate): 78 command buffers a second at 16.2 ms each is 1.27 s of
GPU per second, on one queue. CB spans on one queue cannot overlap here: the CB
end stamp is BOTTOM_OF_PIPE, which Turnip precedes with a wait-for-idle
(tu_query_pool.cc:2122), and concurrent binning is off (drirc
`tu_allow_concurrent_binning` defaults false in the fork; hakuX does not set it).
So command buffers are counted more than once.

The code says where. A finish on the PFIFO thread that is not deferred hands the
submit to the render thread, waits for it, and reads the slot's stamps back
(draw.c:4742). The render thread marked the slot submitted when it submitted it
(render_thread.c:153), and nothing clears that mark. Frame rotation reaches the
same slot as `next_frame` before it is recorded again, sees it submitted, and
reads the same stamps back a second time (draw.c:4803-4807). Every such command
buffer is counted twice in `gpu_total_ns`/`gpu_render_ns`/`gpu_nonrender_ns`
(the `xemu-gpu` Tot/Rnd/Xfr line, the frametrace record's `gpu`) and in
`xemu-xfr`.

The counts agree with that: readbacks per frame (`cbpf`) minus submits per frame
is the non-deferred finishes. T0: 3.00 readbacks, 2.10 finishes, of which 1.0 is
`sd` (a surface download finish, not deferred). D0: 1.13 readbacks, 1.07
finishes, `sd` 0.05. X0 (NG Black) is the row without them: `sd` 0, 1.06
readbacks for 1.07 finishes, and Tot (23.0 ms) under its 25.5 ms frame. So NG
Black's X0 numbers are not over-counted. The render thread's own
synchronous path (draw.c:4648) does not mark the slot, so it is read once.

What this changes and what it does not:

- **Shares inside a command buffer are not affected.** A duplicate read
  repeats one CB's own `in`, `out`, `nr` and categories together, so `out` −
  `in` over `nr` and `nr_out` over `nr` are weighted averages of real per-CB
  values. The verdicts above stand.
- **Absolute per-frame GPU ms are over-counted** on titles with non-deferred
  PFIFO finishes, by the weight of those CBs: on T0 by at least 10 ms of 48.5
  (Tot cannot exceed the 38.4 ms frame). belowbar1005's survey figures (ToeJam
  17.9 ms `nr`, and its Tot/Xfr/Rnd per title) carry the same over-count, and
  so does any "GPU-bound" judgement read from `xemu-gpu` Tot on such a title.
  Titles whose finishes are all deferred or on the render thread (D0: 0.05 a
  frame) are barely touched.

The fix (this attempt, draw.c only, telemetry; nothing that renders reads these
stats): a slot's stamps are read once per recording. A per-slot flag is cleared
when the slot's command buffer begins and set by the first readback; a second
readback of the same recording is skipped and, under `HAKUX_GPUXFR=1`, counted
on the `XFR rp` line as `dup <n> <ms>` (count and summed CB span in that
window). T1 checks it against a known answer (below).

### T1: the readback fix against a known answer (written before queueing)

T1: ToeJam & Earl III, the T0 route (`routes/gnr-toejam`), 300 s, Nova,
perflog, `PERF_REGIMEN=default`, `HAKUX_GPUXFR=1`, at the commit that carries
the fix. Window: `mark gameplay` + 20 s to the end. T0 is its pair (same route,
same env, the build before the fix).

The known answer: T0 has 1.0 `sd` finish a frame (not deferred, PFIFO thread),
and 0.90 more readbacks a frame than finishes.

- **The fix reads the change:** `dup` is within 0.15 of T1's own `sd`
  finishes per frame, and `cbpf` is within 0.10 of T1's finishes per frame.
- **The over-count is gone:** Tot × (`[sdcall]` frames per second) is at most
  1.0 s per s (T0: 1.27).
- **The size of the over-count:** T0's Tot minus T1's Tot is within 25% of
  T1's `dup` ms per frame, if gfps is within 10% of T0's (same scene). If the
  scene moved, only the first two legs are judged.
- **Shares unchanged:** `nr_out` at most 30% of `nr`, as in T0.
- **Fails:** `dup` 0 with `cbpf` still above finishes + 0.5 (another
  double-count path); or `dup` matches but Tot still exceeds the frame time
  (then something else overlaps, and the absolute GPU ms stay unexplained).

### T1 read: the fix reads the known change, and ToeJam is not GPU-bound

T1 `1-1791289531-lane.gpunonrender-3548254`, apk 7e21e360c518 (ref
5c35880d0a), window 05:28:29-05:31:12 (163 s), GPU 401 MHz in every sample, no
thermal pause, battery 80% on USB. The route reached the same overlay scene as
T0. gfps 25.4 and G 38.8 ms in both runs, and the windows hold the same 4260
`[sdcall]` frames.

| per frame | T0 (before) | T1 (fix) | leg |
|---|---|---|---|
| finishes (`sd`) | 2.10 (1.0) | 2.09 (1.01) | |
| readbacks (`cbpf`) | 3.00 | **2.00** | within 0.10 of finishes: 0.09, **pass** |
| `dup` skipped | - | **1.00**, 23.01 ms | within 0.15 of `sd`: 0.01, **pass** |
| `xemu-gpu` Tot | 48.54 | **25.50** | |
| Tot × frames/s | 1.27 s/s | **0.67 s/s** | at most 1.0, **pass** |
| T0 Tot − T1 Tot | 23.04 | | within 25% of `dup` ms (23.01): 0.1%, **pass** |
| Rnd / Xfr | 31.09 / 17.46 | 16.52 / 8.98 | |
| `out` − `in`, share of `nr` | 16.90, 97% | 8.46, 94% | |
| `nr_out`, share of `nr` | 0.55, 3.2% | 0.52, 5.8% | at most 30%, **pass** |
| `download` | 0.46 | 0.46 | |

Every leg passes. The instrument now counts each command buffer once, and the
skipped readbacks are exactly the `sd` finishes. The CB that was counted twice
is the big one: 23 ms of ToeJam's frame.

What it changes:

- **ToeJam & Earl III is not GPU-bound on this scene.** Its GPU frame is 25.5 ms
  inside a 38.8 ms guest frame, 66% busy at 401 MHz. belowbar1005's 52.3 ms Tot
  and 17.9 ms `nr` were about twice the real values. The real `nr` is 9.0 ms,
  and 94% of it is render-pass work. What paces ToeJam at 25 fps is not the
  GPU's work and is not measured here. It is a wait to find (the owner's rule:
  never a faster clock or mode).
- The conclusion on the brief's question does not move. The real between-pass
  GPU time on ToeJam is 0.52 ms a frame.

### Which survey titles carry the over-count

A title's GPU numbers are inflated when it has non-deferred finishes on the
PFIFO thread. From the hakuX-stall `Finish:` counts in each belowbar1005
survey run (`sdscan.py`, over the survey's "a run" column), `sd` finishes per
flip:

| affected (`sd` per flip) | not affected (`sd` ≤ 0.1 per flip) |
|---|---|
| Top Spin 18.3, Midtown Madness 3 5.36, Conker 4.10, Counter-Strike 1.70, Halo 2 1.67, Burnout 1.37, BloodRayne 1.34, Blinx 2 1.30, Forza 1.24, Nightfire 1.23, PGR 1.04, Castlevania CoD 0.94, Azurik 0.93, ToeJam 0.84, Midnight Club 3 0.81, NBA Live 2005 0.67, Otogi 0.42, Fuzion Frenzy 0.42 | NG Black 0, 007 AUF 0, DOA Ultimate 0, Black 0, Kabuki Warriors 0, RalliSport 0, GTA SA 0, Battlefield 2 MC 0, Alias 0, Blinx 0, Tron 2.0 0.02, Crimson Skies 0.04, DOA3 0.05, Ghoulies 0.08, Crash Twinsanity 0.09 |

How much each affected title is inflated is the span of the CBs its `sd`
finishes end. That is 23 ms on ToeJam and is not known for the others from the
old logs. Any "GPU-bound" judgement read from `xemu-gpu` Tot on a title in the
left column, before 5c35880d0a, needs a re-read on a build with the fix.
Non-deferred STALLED finishes go through the same path. The `stl` count does
not say which are deferred, so they are not in this table.

## Attempt 9: why attempt 8 did not finish

Attempt 8 did finish. It read T0/D0/T1, fixed the stamp double count, fixed
the release build, ran preflight and the jobs selftest, and set PR.md to
`State: ready` at 8cb3cdf0e7 (pushed, 06:34 PDT). The resume at 06:40 PDT found
nothing to do: origin/master has not moved past c3a0c70ace, nothing of this
lane is queued or running, and the Nova's last run on the lane APK was
followed by the master restore. The lane's next step is the fold, then the
load/store census lane in "Brief for the next lane".

## Attempt 10: why attempt 9 did not finish

Attempt 9 did finish; there was nothing left to do. The lanewaker's keepalive
pass resumed the lane again at 06:55 PDT. That pass resumes a lane named in
`keepalive-lanes.txt` (this lane, until 07:00 PDT) when its unit is down and
its branch has no WAITING file. A ready lane waiting only for its fold had no
WAITING file. Fix: `docs/lanes/gpunonrender/WAITING` now reads
`fold gpunonrender`. The keepalive pass skips a lane with a WAITING file, and
lanewaker never resumes a folded branch, so the lane stays stopped until its
fold. origin/master is still c3a0c70ace (merged), and nothing of this lane is
queued or running.

## Control, read from the existing counter (attempt 1 arms)

The `xemu-gpu` line already carries `Xfr` = `gpu_nonrender_ms` (profile.c,
the same stats the readback fills), once per second. Per-second medians
over the 150 s run (107 windows C0, 108 windows C16):

| arm | Tot med | Rnd med | Xfr med | Xfr mean |
|---|---|---|---|---|
| C0 (`HAKUX_GPUXFR=1`) | 0.70 | 0.30 | 0.40 | 0.37 |
| C16 (`+ CTRL=16`) | 1.40 | 0.30 | 1.10 | 1.10 |

Xfr rises by 0.70 ms per frame, Rnd does not move, and Tot moves by the same
0.70. That is the pre-stated pass shape for `nr`. A 16-copy total of 0.70 ms
is about 0.044 ms per 1 MiB copy. This is partial: the per-category `ctrl`
value needs the `xemu-xfr` line, which the re-run below emits.

These arms are menu frames. The route runs the publisher logos, the title and
the main menu, and the 150 s soak did not reach NG Black gameplay. That is fine
for a control of a known cost. It is not a gameplay reading, and the title
measurements need a route that reaches gameplay.

Results: the attempt-1 arms are read above. The attempt-2 re-run (same route,
same env, fixed tag) is the instrument verdict; see the Attempt 2 section below.

## Measurement plan after the control

Per title, a 120-180 s perflog soak with `HAKUX_GPUXFR=1`, the same route as
belowbar1005 used where one exists. Titles and devices:

| title | device (per titlepush listing) | route |
|---|---|---|
| NG Black | Nova | `bb-ngb.route` |
| DOA3 (dojo stage) | Thor | `bb-doa3.route` |
| Otogi | Thor | none yet |
| ToeJam & Earl III | Nova | none yet |
| 007 Agent Under Fire | Nova (refused-dup list: staged there) | none yet |
| DOA Ultimate | check `titlepush/listing-*.txt` before queueing | none yet |

A route must be written for each title without one. The Thor runs are cold
slots only, at most 480 s, stopped at xo 70 C; a run after a thermal pause
voids its fps. The overhead arm (`HAKUX_GPUXFR` unset, same title, same route)
is queued once, on the title with the most brackets.

Per title, per category, the table is median/mean/p90 ms per frame, ops per
frame, the largest category's share of `nr`, the residual share, the dropped
count, and the GPU clock from thermal.jsonl for the same window.

## Decision rules (fixed before the readings)

- "This category is the cost": one category holds at least 50% of
  `gpu_nonrender_ms` (mean over windows) in at least 3 of the 6 titles. The
  category may differ between titles; the rule is about one dominant category
  across titles, so the single next lane is that one.
- "It is not": no category reaches 50% in at least 3 of the 6 titles. Then the
  next step is the largest site inside the largest category, or the aux CB
  (gap 1), whichever the residual points to.
- Residual above 15% of `nr` in a title: say what is outside the brackets
  (gap 1 or 2), and do not rank that title's categories as complete.

## Ranking

Row 1 below was measured by the render-pass census (N0, D1, "Render-pass
census" at the end of this file): the avoidable loads and stores are worth at
most 0.4 ms a frame, and the lever is the scene passes' render mode.

Final after T0 and D0 (three titles under the outer stamps: NG Black, ToeJam &
Earl III, DOA3). Ranked by P × win.

The answer to the brief's question: on all three titles, 94-98% of
`gpu_nonrender_ms` is render-pass work that the in-pass stamps cannot see
(Turnip's binning, every tile but the last, and the tile loads and stores). The
GPU's real time between render passes is 0.26-0.52 ms a frame, and its largest
category is `download` (site 587) on every title. No upload, copy, conversion
or barrier fix can win the 5-18 ms the survey suggested. The time is inside the
render passes.

| # | candidate | P (evidence) | win | cost |
|---|---|---|---|---|
| 1 | **Render-pass cost on the tiler**: per pass, GMEM vs sysmem, bin count, and which attachments are loaded and stored per tile. The code today: `get_optimal_color_load_op`/`get_optimal_zeta_load_op` (draw.c:3567-3593) LOAD any initialised surface, so a pass that begins with a full guest clear still loads every tile first; and every colour and depth/stencil attachment is STOREd (draw.c:1774-1794), including a depth buffer nobody reads after the pass. Every pass break (`render_pass_breaks`) pays a full load and store of each attachment. | 0.35. For: the outer stamps put 94-98% of the "non-render" time inside passes on all three titles, at 0.87 (NG Black), 0.91 (ToeJam, T1) and 6.2 (DOA3 fight, 2.1 big passes) ms per pass outside the last tile. `TU_DEBUG=sysmem` gained 8 gfps on DOA and AUF (lane.flip474), so per-pass mode alone moves fps there. Against: no per-pass census exists, some loads are required (the guest draws over the previous contents), and the bins/tiles part is inherent to GMEM | NG Black: GPU-bound at 680 MHz, 23 ms GPU frame (X0 is not over-counted: no `sd` finishes); 3-6 ms off it is 28.5+ in most windows. DOA3's fight: 26.4 ms GPU in a 31.4 ms frame at 680 MHz. Not ToeJam: T1 shows its GPU 66% busy, so a GPU win does not move its fps. AUF and DOA Ultimate have no `sd` finishes, so their survey Tot stands; reached if they behave as these titles (not run) | First a measurement, telemetry only: a per-pass census under `HAKUX_GPUXFR=1` (attachment sizes, load/store ops, whether the first draw is a full clear, draws, outer span per pass), one NG Black run and one DOA3 run. Then the fix lane. Brief below |
| 2 | Forza and Midnight Club II: texture.c:2100's surface-range scan completes a pending download because the texture reads a rendered surface through VRAM | 0.35 (unchanged; needs one counter: why the bind does not take the surface-to-texture path) | Forza 8-19 ms per frame of PFIFO wait, MC2 8.0 | a counter, then the fix lane |
| 3 | (A) on Spider-Man 2: the splice's eligibility check refused every update (S1) | 0.15. The refusal reason is not counted; if it is a swizzled download, the splice needs a GPU swizzle; and F1 showed the wait can move to `range` once `surfupd` is gone | up to 6 ms per frame, 26.8 to ~30 fps, one title | a refusal-reason counter, one run, then possibly a GPU swizzle |
| 4 | Simpsons, the STALLED submit or the lock across its wait | 0.05. Both halves are refuted: simp2 (lock) and K1 (submit) each lost fps | none expected | a frametrace capture of K1 would name where the PFIFO thread holds pfifo.lock, if anyone wants the reason |
| - | In-pass stamp cost in the shipped build | refuted by X1 (+0.5% per pass with the stamps removed) | none | none |

| - | Absolute GPU ms in `xemu-gpu` (Tot/Rnd/Xfr) on titles with non-deferred PFIFO finishes | fixed in this lane (5c35880d0a, a slot's stamps read once); T1 passed its known answer | correct "GPU-bound" judgements: ToeJam's Tot fell from 48.5 to 25.5 ms on the same scene. 18 survey titles carry the over-count (table above) | done |
| - | What paces ToeJam at 25 fps with the GPU 66% busy | not measured here | ToeJam is a survey title, not a ledger one | a frametrace capture names the wait |

By the brief's decision rule, no category is "the cost": on NG Black, ToeJam
and DOA3 the largest (`download`) is 2-5% of `nr`. The single next lane is (1),
and its first step is the per-pass census, because "which attachments are
loaded and stored per tile, and which of those loads are overwritten by a clear"
is a guess until it is counted.

### Brief for the next lane: render-pass load/store on the tiler (#433)

What the GPU does inside a render pass, beyond the guest's draws. On NG Black,
ToeJam & Earl III and DOA3, 96-98% of what belowbar1005 measured as
"non-render" GPU time is inside the render passes (docs/lanes/gpunonrender/NOTES.md,
X0 and "T0 and D0 read"): binning, every tile but the last, and the tile loads
and stores. The emulator's choices that set the load/store part:

- `get_optimal_color_load_op` / `get_optimal_zeta_load_op` (draw.c:3567-3593)
  return LOAD for any initialised surface. A pass whose first guest operation
  clears the whole surface still loads every tile, then clears it.
- Render-pass attachments are created with `storeOp` STORE for colour and for
  depth and stencil (draw.c:1774-1794). A depth buffer that no later pass,
  texture or download reads is still written out for every tile.
- Each pass break stores every attachment and the next pass loads them again.

Step 1, telemetry only (default off, `HAKUX_GPUXFR=1`): per pass, record the
attachment formats and sizes, the load/store ops chosen, whether the first
operation in the pass is a clear covering the whole render area, the number of
draws, and the pass's outer span (the outer stamp pair exists:
`xfr_rp_outer`). Report per frame: passes, passes whose LOAD is followed by a
full clear, passes whose depth is never read after the pass, and the outer ms
in each group. One NG Black run (`bb-ngb`) and one DOA3 run (`bb-doa3`; the
fight before 05:13 in D0 ran at 680 MHz with the GPU 84% busy). Not ToeJam:
with stamps read once its GPU is 66% busy (T1), so a GPU saving does not move
its fps. Use a build at or after 5c35880d0a, so the GPU ms count each command
buffer once.

Expected result to write before the runs, and the decision: if the passes with
an avoidable load or store carry at least 30% of the outer render span, step 2
is the fix (LOAD to CLEAR or DONT_CARE when the first operation is a full
clear; DONT_CARE store for a depth attachment whose next use is a clear or
nothing), behind an env switch, default off, with a golden arm. If they carry
less, the remaining cost is bins and tiles (GMEM itself), and the next step is
per-pass GMEM vs sysmem (lane.rendermode474's area), not load/store.

Cost: one draw.c telemetry commit and two Nova runs for step 1. P(step 2 wins
at least 3 ms a frame on NG Black) 0.35.

## Attempt 11: why attempt 10 did not finish

Attempt 10 did finish. It was waiting for the fold, and the fold landed
(0342eba317). lane.local resumed the lane at 10:20 PDT 10-06 with new scope:
step 1 of "Brief for the next lane" above, the render-pass load/store census.
This attempt merged origin/master (fast-forward to 0342eba317) and deleted the
fold WAITING file.

## Render-pass census (step 1 of the brief above)

### The instrument (draw.c, surface.c, texture.c; `HAKUX_GPUXFR=1`, default off)

Each pass that has an outer stamp pair also gets a census record. At readback
the record is filed with the pass's outer span, its in-pass span, and a mode
inferred from the two. A new pair of lines, `xemu-xfr XFR rpc` (every pass) and
`xemu-xfr XFR rpc g` (passes read as GMEM), gives per command buffer, for each
group: passes, outer ms, and avoidable MiB.

| group | the pass... | avoidable bytes |
|---|---|---|
| `all` | every pass | - |
| `lclr` | LOADs an attachment whose first operation in the pass is a clear covering the whole binding | that attachment |
| `lunif` | LOADs an attachment whose content is a whole-binding clear with nothing after it (a clear-only pass before it, typically) | that attachment |
| `zdead` | STOREs a depth/stencil attachment whose next use is a whole-binding clear or a full upload (no draw with depth or stencil, partial clear, download, copy or bind as texture in between) | the depth attachment |
| `clronly` | has a clear and no draw | - |
| `any` | `lclr`, `lunif` or `zdead` | the larger of the two loads, plus the dead store |

Also per command buffer: `ldMB` (all LOADed attachments), `stMB` (all stored),
`in` (in-pass span of the paired passes), `draws`, `paired` (passes with both
stamp spans), `zlive`/`zpend` (depth stores read later / still unresolved at
readback), and `late` (dead/live resolved after their CB was read).

Mode inference: Turnip writes an in-pass stamp into the pass's draw stream,
which a GMEM pass replays per tile, so its in-pass span is the last tile; a
sysmem pass is stamped in full. A pass whose in-pass span is under 0.8 of its
outer span reads as GMEM. In a sysmem pass a LOAD or STORE op emits nothing,
so only the `g` line's bytes are real tile traffic.

Draws are counted in `begin_draw` (a draw "uses" the colour attachment when a
colour write mask is on, the depth attachment when Z or stencil test is on) and
in `emit_reorder_entry` (its own `color_write`, `depth_test`, `stencil_test`).
Surface content and pending depth stores are kept per `SurfaceBinding` in a
32-entry table. A freed surface is dropped (`destroy_surface_image`); a pointer
reused after a free can at worst read as unknown content.

NDK clang, perflog and release, `-Wall`: no new warnings.

### What is already on disk (X0, D0), and what it predicts

From the existing perflog lines of X0 (NG Black) and D0 (DOA3 fight, 05:11:00-
05:11:30 at 680 MHz), per frame:

| | NG Black X0 | DOA3 D0 fight |
|---|---|---|
| render passes (`XFR rp` n, per CB) | 12.7 | 2.0 |
| clears (`xemu-work` Clr) | 3 | 2 |
| inline clears, hits/misses (`InlClr`) | 0 / 3 | 1 / 1 |
| `rp_break_clear` (a clear-only pass ending) | 3 | 1 |
| outer span / in-pass span per CB (ms) | 14.6 / 9.0 | 44.0 / 22.0 |
| draws per frame (`xemu-work` BE) | 260-390, ~20 per pass | ~1500, nearly all in one pass |
| `surface_scale` | 1 (640x480) | 1 |

So NG Black opens 3 clear-only passes a frame (a clear arriving with no pass
open gets a pass of its own, `pgraph_vk_clear_surface`'s fallback), and DOA3
opens 1, followed by one big pass whose in-pass span is half its outer span.
In this Turnip fork a pass with fewer than 5 draws runs sysmem
(tu_autotune.cc, "Too few draws to tune" returns `default_mode`, which is
`SYSMEM`), so the clear-only passes are sysmem, and the pass after each one
LOADs a surface that holds nothing but the clear.

At scale 1, a 32-bit 640x480 attachment is 1.2 MiB. The lane's own control
(C16) measured a 1 MiB buffer-to-buffer copy, read plus write, at 0.043 ms. A
tile load or store moves its attachment once between memory and GMEM, so
0.043 ms per MiB is an upper bound on what each avoidable MiB costs in bytes.

### Runs and their expected results (written before queueing)

Both on the Nova, perflog, `PERF_REGIMEN=default`, `HAKUX_GPUXFR=1`, at the
census commit. Window: `mark gameplay` + 20 s to the end (NG Black); the fight
frames for DOA3 (the route's frames say where the fight ends).

| arm | title, route, s |
|---|---|
| N0 | NG Black, `belowbar1005/routes/bb-ngb`, 480 |
| D1 | DOA3, `belowbar1005/routes/bb-doa3`, 480 |

**Instrument legs (known answers; if one fails, the census is not read):**

- K1: `rpc all` passes per CB equal the `XFR rp` n of the same window, within
  0.05 (they count the same passes).
- K2: `rpc clronly` passes per frame equal the inline-clear misses per frame of
  the same window (`InlClr` second figure / 60), within 0.3.
- K3: clear-only passes read as sysmem: `rpc g clronly` n is at most 0.1 of
  `rpc clronly` n. If K3 fails the mode inference is wrong, and only the
  all-pass figures are read.
- K4: `paired` is within 0.1 of `rpc all` n (fewer than 48 passes per CB).

**Expected:** NG Black, `clronly` about 2.8 per CB and `lunif` 2-3 per CB, with
`zdead` at least 1 per CB. DOA3, `clronly` 1 and `lunif` 1 per CB, the `lunif`
pass being the big GMEM pass. On both, the `g any` passes carry at least 30% of
the outer span (the scene passes are the ones after the clears), and the
avoidable bytes are small: `g any` at most 8 MiB per frame on NG Black and
4 MiB on DOA3, which is at most 0.35 ms and 0.17 ms per frame.

**Decision (fixed before the runs):**

- Leg S, the brief's rule: `rpc g any` ms is at least 30% of `rpc all` ms.
- Leg B, the size: `rpc g any` MiB per frame x 0.043 ms is at least 1.0 ms per
  frame on NG Black. Leg B is added here, before any run, because the share in
  leg S cannot size the win: a pass with one avoidable load carries its whole
  span into the group, and the fix removes only the load.
- S and B both hold: step 2 (a CLEAR load op when the pass's first operation is
  a whole clear, or when the surface holds only a clear; DONT_CARE store for a
  dead depth), behind an env switch, default off; one A/B on NG Black (600 s,
  frames every 30 s, read from fps_ok and GPU ms) and a frame pair.
- S fails, or B fails: no load/store A/B. The remaining GMEM cost is bins and
  tiles, and the census's `g` line gives its size per pass (`g all` ms − `g in`
  ms, against `g draws`). That goes to lane.rendermode474's area as a per-pass
  GMEM-vs-sysmem recommendation, and the lane stops at ready.

My expectation is S holds and B fails on both titles: P(step 2 is triggered)
about 0.15. What B does not see: a fixed per-tile cost of each load or store
blit beyond its bytes. If B fails while `g all` − `g in` is large per pass and
`g` passes are few, that fixed cost is the open question, and the
GMEM-vs-sysmem lever covers it either way.

### N0 read: NG Black

`1-1791306758-lane.gpunonrender-630725`, ref f4ffe285e7, apk 281bf2515bb8
(dispatcher: `shader cache cleared: apk 6beaa5ac1cdd -> 281bf2515bb8`).
Window 10:18:33-10:21:40 PDT (187 s from `mark gameplay` + 20 s), 6240 frames,
1.05 CBs per frame. Gameplay in the canyon in every hold frame (FPS 36 on the
overlay). gfps 36.3, G 29.9 ms. GPU 475-680 MHz in the window, no thermal pause.
Battery 80%, on USB (5.8 W in). `xemu-gpu` Tot 24.6 ms (X0: 23.0), `nr_out`
0.42 ms, as X0. Reader: `rpcread.py <id> --from 10:18:30.8`.

Per frame:

| group | every pass: n / outer ms / avoidable MiB | passes read as GMEM: n / ms / MiB |
|---|---|---|
| `all` | 13.08 / 24.53 / - | 5.18 / 22.95 / - |
| `lclr` | 3.00 / 0.08 / 4.33 | 2.04 / 0.03 / 0.53 |
| `lunif` | 3.14 / 19.88 / 4.33 | 1.23 / 19.46 / 3.64 |
| `zdead` | 0.27 / 0.24 / 0.39 | 0.15 / 0.16 / 0.15 |
| `clronly` | 3.00 / 0.08 / - | 2.04 / 0.03 / - |
| `any` | 6.06 / 20.18 / 9.02 | 3.10 / 19.65 / 4.30 |
| `ldMB` / `stMB` (all attachments) | 21.8 / 21.8 | 8.9 / 8.9 |
| in-pass span `in` | 12.82 ms | 11.28 ms |
| draws | 351 | 273 |

Depth stores: 6.41 a frame read later (`zlive`), 0.27 dead, 0.01 pending at
readback.

Instrument legs: **K1 pass** (0.002 per CB), **K2 pass** (clear-only passes 3.00
a frame against 2.97 inline-clear misses, 0 hits), **K4 pass** (every pass
paired). **K3 fails**: 2.04 of the 3.00 clear-only passes read as GMEM. A
clear-only pass spans 0.03 ms, where the fixed cost of the stamps and the pass
setup decides the in/out ratio, so the 0.8 rule cannot tell a tiny pass's
mode. By the rule written before the run, only the all-pass figures are read.
Leg B does not need the mode split: it is bounded by every pass's bytes.

Decision legs:

- **S holds**: the passes with an avoidable load or store carry 82% of the outer
  span over every pass (20.18 of 24.53 ms). As expected, they are the scene
  passes: each of the 3 clear-only passes is followed by a pass that LOADs a
  surface holding only that clear (`lunif` 3.14 a frame, 19.9 ms).
- **B fails**: the avoidable traffic over every pass is 9.02 MiB a frame
  (expected at most 8), so at most 9.02 x 0.043 = **0.39 ms a frame**. Even every
  load and store of every pass (43.6 MiB) bounds at 1.9 ms.

So on NG Black the load/store fix would remove at most 0.4 ms of a 24.6 ms GPU
frame: no A/B for it. What the GMEM passes cost beyond their last tile is
**11.7 ms a frame** (out 24.53 − in 12.82 over every pass; 22.95 − 11.28 on the
GMEM-read passes), almost all in the ~3 scene passes: about 3.7 ms per scene
pass, of which loads and stores are at most 0.6. The rest is binning and the
tiles before the last, the part that only the per-pass render mode moves.

### D1 read: DOA3

`1-1791306763-lane.gpunonrender-631156`, ref f4ffe285e7, apk 281bf2515bb8
(the N0 apk; no cache clear between them). The route reaches a fight on the
street stage at 10:24:58 and loses it at 10:26:08 ("YOU LOSE"); after that it
is the attract screens (title over 3D stages). Fight window 10:25:00-10:26:00,
**60 s, not the 180 s the telemetry bar names**: the route loses within a
minute, as it did in D0. The census is a per-pass structure, and the fight's
reading matches D0's fight (2 passes a frame, one inline clear and one
clear-only pass, in/out 0.50), so it is read, with the attract screens beside
it as a second scene. GPU 680 MHz through the fight, no thermal pause, battery
80% on USB (6.2 W in). Fight: gfps 22.0, G 44.0 ms, `xemu-gpu` Tot 38.5 ms (the
GPU 87% busy).

Per frame:

| group | fight, every pass | fight, GMEM-read | attract, every pass | attract, GMEM-read |
|---|---|---|---|---|
| `all` n / ms | 2.33 / 38.73 | 1.33 / 38.43 | 3.29 / 18.31 | 1.61 / 16.98 |
| `lclr` n / ms / MiB | 1.00 / 0.04 / 3.94 | 0.06 / 0.00 / 0.23 | 1.33 / 0.04 / 4.24 | 0.52 / 0.01 / 1.04 |
| `lunif` | 1.00 / 34.96 / 3.94 | 0.99 / 34.83 / 3.90 | 1.43 / 16.73 / 4.49 | 0.94 / 16.12 / 3.68 |
| `zdead` | 0.35 / 11.98 / 0.94 | 0.33 / 11.90 / 0.89 | 0.57 / 5.46 / 1.33 | 0.37 / 5.27 / 0.98 |
| `clronly` | 1.00 / 0.04 | 0.06 / 0.00 | 1.33 / 0.04 | 0.52 / 0.01 |
| `any` | 2.08 / 36.34 / 8.82 | 1.12 / 36.13 / 5.02 | 2.80 / 17.23 / 9.80 | 1.51 / 16.48 / 5.64 |
| `ldMB` = `stMB` | 9.23 | 5.26 | 10.92 | 5.32 |
| `in` ms | 19.48 | 19.19 | 9.70 | 8.44 |
| draws | 716 | 704 | 341 | 312 |

Instrument legs, fight: **K1, K2, K3, K4 all pass** (K3: 0.06 of 1.00 clear-only
passes read as GMEM). Attract: K1, K2, K4 pass, K3 fails (0.52 of 1.33), as on
NG Black: a clear-only pass is too short for the ratio.

Decision legs, fight: **S holds** (93%), **B fails**: 5.02 MiB a frame on the
GMEM passes, 0.22 ms; over every pass 8.82 MiB, 0.38 ms. Attract: S holds (90%),
B fails (0.24 ms; 0.42 over every pass).

### The decision: no load/store A/B; the lever is the render mode of the scene passes

The rule written before the runs: S and B must both hold for step 2. B fails on
both titles by a factor of 2.5 or more even when every pass's bytes are
counted, so **no load/store fix is built and no A/B is queued**. The census
shows why the share in leg S was the wrong measure: the passes that carry an
avoidable load are the scene passes themselves (each follows a clear-only
pass), so they carry the frame, but what is avoidable in them is one 1.2 MiB
load each.

What the GMEM scene passes cost beyond their last tile, from the same lines:

| | GPU frame (`xemu-gpu` Tot) | outer span | in-pass span (last tile) | out − in | scene passes | draws per scene pass | avoidable bytes, bound |
|---|---|---|---|---|---|---|---|
| NG Black (N0) | 24.6 ms | 24.53 | 12.82 | **11.7 ms** | ~3 | ~90 | 0.39 ms |
| DOA3 fight (D1) | 38.5 ms | 38.73 | 19.48 | **19.3 ms** | 1 | ~700 | 0.38 ms |
| DOA3 attract (D1) | | 18.31 | 9.70 | **8.6 ms** | ~1 | ~310 | 0.42 ms |

On the DOA3 fight the one scene pass spends 38.4 ms in GMEM and 19.2 ms in its
last tile: in/out 0.50, the pattern lane.flip474 measured on DOA Ultimate,
where "GMEM rendering executes DOA's draw stream twice, and sysmem once", and
`TU_DEBUG=sysmem` took the fight from 14-16 to 21 gfps (Tot 58-64 to 41 ms).
That is a draw-replay cost (each bin replays all ~700 draws), not bytes.

### Recommendation for lane.rendermode474's area (per-pass GMEM vs sysmem)

Ranked by P x win. All three are render-mode changes in the driver's code
path, judged by fps and J/frame as gmem474 did, not a clock or a power mode.

| # | candidate | P (evidence) | win | cost |
|---|---|---|---|---|
| 1 | DOA3 (`54430001`) to `sysmem` in `kTitleRenderModes` (xemu_android.cpp), after an A/B | 0.55. For: D1's fight pass is one GMEM pass with ~700 draws at in/out 0.50, the signature of DOA Ultimate, which sysmem took from 14-16 to 21 gfps; the GPU is 87% busy at 680 MHz. Against: Kabuki's fight stalled under sysmem (gmem474), and DOA Ultimate's sysmem arm changed the ZPASS report in the pgraph suite (flip474 `sysmem.md`; shipped as an exception) | fight: GPU 38.5 ms toward ~29 ms at DOA Ultimate's ratio (one sysmem execution 19.3 ms against 12.6-12.8 per GMEM replay, 1.5x; here a replay is ~19.2 ms); G 44 ms toward ~35, 22 gfps toward ~28 if the GPU stays the pacing wait | one A/B on `bb-doa3` (default vs `--env TU_DEBUG=sysmem`), census on in both arms, 480 s each, read in the fight; then a one-line table entry |
| 2 | Per-pass mode in the Turnip fork's autotune: a pass with many draws whose bin count is small runs sysmem (the replay cost grows with draws times bins; the fill cost of sysmem grows with pixels) | 0.3 until #1 and #3 are measured; the fork already chooses per pass (tu_autotune.cc), so the lever exists | reaches every replay-bound title without a table entry; size unknown | a fork change; needs the per-pass bin count, which the census does not have |
| 3 | NG Black (`5443000D`) to `sysmem`, after an A/B | 0.3. For: 11.7 ms of a 24.6 ms GPU frame is outside the last tile of ~3 GMEM scene passes. Against: ~90 draws per scene pass, so less replay-bound than DOA3; flip474 did not measure NG Black | up to ~10 ms of the GPU frame if replay dominates; 36 gfps toward 45 | the same A/B on `bb-ngb` |

A check that comes free with the A/Bs: in a `TU_DEBUG=sysmem` arm every pass is
sysmem, so the census's `g` line must read near 0 passes and `in` near `out`.
That is the known answer the mode inference (K3) still lacks on large passes.

For whoever resumes this: the census's mode inference cannot classify a pass
shorter than ~0.1 ms (K3 fails there). A fix that reads the mode should test
the ratio only above a minimum outer span. The load/store groups do not depend
on it.

### Where attempt 11 stopped

Done: census telemetry (f4ffe285e7), N0 and D1 read against the rule written
before them, the restore at master ran, `nv2a_index.json` regenerated, PR.md
`State: ready`. preflight passes every gate but `coverage`, which fails on
board rows for open issues #852-#857 (fighting-game hold work, not this lane's
files). Nothing of this lane is queued or running. WAITING is `fold
gpunonrender` again, so the keepalive pass leaves the lane stopped until the
fold.
