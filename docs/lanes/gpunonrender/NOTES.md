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

To be written after the six titles. Candidates are ranked by P x win, with the
win stated per title as ms/frame and fps, and each avoidable/inherent call
backed by the code path and the op counts, not a guess.
