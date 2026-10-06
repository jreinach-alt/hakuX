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
