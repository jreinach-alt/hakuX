# lane.forzadecay414 -- Forza's 29 -> 3 fps decay: clock or game? (#414 item 1)

Base master 85347ffbd1. Title 4D53006E (Forza Motorsport), survey route, both handhelds.
Reader: `docs/lanes/forza414/timeline.py <logcat>` (30-s rows, t = 0 at `soak start`);
scratch scripts that walked `dispatch/results/*` are not committed. The `fps` column below is
timeline.py's (flips from gfps lines per bucket), so it differs a little from the brief's
curve, which came from another reader. The last bucket (t = 420) is a partial window in every run.

## 1. Every Forza soak on disk

17 soaks with a logcat (`request.json` title `4D53006E`). One more, `1790450270-forza414-1731994`,
is `ERROR: title not on device` (the Nova, before the ISO was staged). `thermal.jsonl` exists only
from the flip474 pair onward. `inv` is the `[watch311]` line's `invalid=`, the length of
`r->invalid_surfaces`.

| result | device | ref | 30-s fps, t = 0..420 | max inv | xo start -> end | hottest cpu zone | pause engaged at t |
|---|---|---|---|---|---|---|---|
| `0-0-x-1790525921-forza414-1054756` | nova | 4b22f2526b | 14 28 30 20 10 18 20 22 26 22 30 28 30 28 4 | 91 | not recorded | - | - |
| `0-0-x-1790525923-forza414-1055334` | nova | 94f002d309 | 14 30 28 22 10 20 18 26 26 24 30 28 30 28 6 | 240 | not recorded | - | - |
| `0-0-x-1790533007-forza414-3417242` | nova | 7787feb2ae | 14 30 28 22 8 20 20 22 26 24 30 28 30 30 2 | 62 | not recorded | - | - |
| `0-0-x-1790533010-forza414-3422338` | nova | 51721e36aa | 14 30 28 22 10 20 20 22 26 24 30 30 28 30 | 72 | not recorded | - | - |
| `1-1790492278-slowdown462-690198` | nova | e5db66fa37 | 12 30 28 24 8 18 20 22 28 24 20 20 14 - - | 143 | not recorded | - | - |
| `1-1790518618-forza414-1930404` | nova | 4b22f2526b | 12 30 28 22 8 18 20 22 26 24 26 24 28 28 | 50 | not recorded | - | - |
| `0-0-y-1790408503-titlebench-8` | thor | 6561442869 | 12 30 30 30 30 28 30 30 26 (front end only) | 11 | not recorded | - | - |
| `0-0-y-1790433159-titleplay-p1-forza` | thor | a5b5b628f2 | 10 30 28 22 6 12 12 14 14 20 **2 4 4 2** - | 188 | not recorded | - | - |
| `1790450265-forza414-1731727` | thor | dc38b745b8 | 14 30 28 24 8 14 14 14 16 20 18 16 18 20 2 | 52 | not recorded | - | - |
| `1790467161-titlebench-2613303` | thor | d0e30924f8 | 12 30 28 20 2 16 14 14 **2 4 2 4 4 2** - | 65 | not recorded | - | - |
| `0-0-x-1790549041-flip474-1818830` | thor | 09fdca3ba1 | 12 30 28 24 2 16 14 14 14 18 **6 4 2 4** - | 138 | 67.4 -> 73.8 (78.1 at t = 300) | 95.4 | **330-420** |
| `0-0-x-1790549042-flip474-1819047` | thor | 09fdca3ba1 | **- 4 8 6 4** 12 14 14 16 20 20 **4 4 2 2** | 61 | 73.1 -> 74.6 (78.0 at t = 330) | 95.0 | **0-120, 360-420** |
| `1-1790552636-forza414-3224517` | thor | 35ee65562a | 12 30 28 24 4 18 18 18 20 24 22 22 24 22 8 | 147 | 60.4 -> 76.0 | 95.0 | none |
| `1-1790561602-forza414-3260817` | thor | 53c81b1a7a | 14 30 28 24 4 18 18 16 22 24 18 20 20 18 6 | 90 | 53.4 -> 78.0 | 95.8 | none |
| `1-1790613195-forza414-3088454` | thor | fa56a26f1f | 12 30 28 24 6 **12 10 8 6 6 6 4 6 4 2** | **4099** | **44.7** -> 72.6 | 95.0 | none |
| `1-1790619761-forza414-1092424` | thor | fa56a26f1f | 14 30 28 22 6 **12 8 8 6 6 6 4 4 4 2** | **3796** | 58.5 -> 74.8 | 96.2 | none |
| `1-1790619761-forza414-1092523` | thor | b991fb4c21 | 14 30 28 24 4 **12 10 8 6 4 6 4 4 4 2** | **3679** | 61.7 -> 75.1 | 96.2 | none |

(`1-1790613195-forza414-3088504` aborted before its first input and has no rows.)

- **There is a Nova Forza race: six soaks, none decays.** 18-30 fps through the race to the end.
  All six are on refs from before #517 (section 3), so they do not separate the device from the
  code.
- **There is a cold-started Thor run on the decaying code:** `3088454`, xo-therm 44.7 C at the
  start, below the brief's 50 C bar. It decays exactly like the two warm runs (58.5 and 61.7 C):
  12 -> 2 fps from the same bucket, with no cooling device at any sample and xo never above 72.6.
- **A Thor run held its race rate with the big cores at 95 C the whole way:** `3260817`
  (53c81b1a7a), with `cpu-1-*` at 92-96 C from t = 30 to the end and xo climbing to 78.0 C,
  ran 16-24 fps from t = 150 to t = 390. `3224517` (35ee65562a) did the same at 94-95 C: 18-24 fps.

## 2. Two different mechanisms, and neither is H1

The decaying runs fall into two regimes with different signatures. They were read as one curve.

**Regime S, the step: the xo-therm 78 C thermal pause (#507).** One step into 2-4 fps with the
renderer mostly idle (Ri 150-290 ms of a 250-400 ms flip), vCPU time down from ~1900 to
~1300-1400 ms per 2 s, and audio zero-filled 35-52%. This is lane.forza414's NOTES section 1
signature. Where `thermal.jsonl` exists, it lands in the bucket where xo-therm reaches 78 C, and
the next sample shows `thermal-pause-F8` (cpus 3-7 paused) and the kgsl devfreq cap engaged.
`0-0-x-1790549042-flip474-1819047` shows both directions. It starts paused (xo 73 C after the
previous arm), at 4-8 fps. It recovers to 12-20 fps once the pause releases at t = 150. It steps
back to 2-4 fps at t = 330, when xo reaches 78.0 C. The two older Thor runs with the same
signature (`titleplay-p1-forza`, `titlebench-2613303`) have no thermal log, so their pause is
inferred from the signature, not read. This is visible heat throttling, already owned by #507.
It is not the brief's H1: that one was invisible LMh/DCVS capping at the junction limit.

**Regime L, the linear decay: `r->invalid_surfaces` grows without bound.** It is the curve in the
brief: 12 -> 2 fps over the race, with no step. It is present in exactly the three runs on
fa56a26f1f and b991fb4c21, and absent in every other run on either device. In `1092424`, per
30 s from t = 150: `inv` 918, 1461, 1935, 2305, 2625, 2948, 3234, 3463, 3691, 3796, with
`[watch311] live` tracking it (each dirty invalid surface keeps its CPU-access watch). G (flip
interval) rises 81 -> 287 ms, the TB invalidate calls per 2 s rise 22750 -> 42274, and the
vCPU's time falls 1816 -> 1524 ms per 2 s. Audio never starves (0%), and no cooling device
engages. The `txw` probe names where the frame's time goes. `scan`
(`pgraph_vk_download_surfaces_in_range_if_dirty`) runs at a steady ~780-930 calls per flip, but
its time climbs linearly: 0.84 ms/flip at 11:26:02, 5.42 at 11:26:36, 13.14 at 11:27:45 and 25.56
at 11:30:44 PDT, which is ~1 us per call at the start and ~33 us per call at the end. `faf`
(`pgraph_vk_flush_all_frames`) is 0.00 calls per flip in every race line.

**The verdict on H1 and H2.** Neither holds as written.
- **H1 (hardware clock capping near the junction limit) is refuted as the cause of either
  regime.** Every H1 prediction fails on data already on disk. The cold start (`3088454`, 44.7 C)
  does not delay the decay. The big cores sit at 94-96 C in runs that do not decay
  (`3260817`, `3224517`). And the decay tracks a list length, not a temperature: `3088454`
  reaches 2 fps at xo 72.6 C, while `3260817` holds 18 fps at 78.0 C. If LMh caps the big cores
  at 95 C, it caps them equally in the runs that hold their rate, so it is not what separates them.
  The clock fields (section 4) will show whether it caps at all. They are not needed for this verdict.
- **H2 as framed (a game-state regime, the same point in the game regardless of temperature or
  device) is half right.** The decay is temperature-independent, but it is not the game's state.
  It is the emulator's: a surface list that stopped being pruned. It began with one commit
  range and does not appear on any earlier ref, on either device.

## 3. Why the list grows (read in code; the bisect arm tests it)

- `invalidate_surface()` (vk/surface.c:2747) stamps a surface invalidated inside the open command
  buffer with `invalidation_frame = r->current_frame`. That is a ring-slot index, and nothing
  resets it afterwards (the only other writes are -1 at creation and for a surface invalidated
  outside a command buffer).
- `surface_in_flight()` (surface.c:3305) is `f == r->current_frame || frame_submitted[f]`. In
  steady state every slot other than the current one is submitted: a slot's flag is cleared only
  as it becomes the next frame (draw.c:3790), and it then becomes current. So a stamped surface
  reads as in flight forever.
- `prune_invalid_surfaces()` (surface.c:3332) skips an in-flight surface. The only thing that
  makes one prunable is `pgraph_vk_flush_all_frames()` (draw.c:3398), which clears every
  `frame_submitted[]` at once, so any slot that is not current reads false until it is submitted
  again.
- **#517 (lane.drain474, fold 09050ddbe5)** moved that flush in `create_texture` from before every
  surface-to-texture bind of a recently submitted surface to the copy branch only. Forza's race
  binds directly, so after #517 nothing flushes there: `faf` 0.00 per flip. Before #517 the
  flush ran on those binds and the list stayed at 10-240. The 24 soaks of other titles on refs
  containing #517 (Blinx, AUF, DOA, Crimson Skies, Otogi, Kabuki) all peak at `invalid` 10-11. Either they
  do not invalidate surfaces inside the command buffer, or something else flushes for them.
- The cost: `pgraph_vk_download_surfaces_in_range_if_dirty` walks `invalid_surfaces` on every
  texture bind (surface.c:467), about 800 times a flip, and the dirty ones keep their CPU-access
  watch, so guest stores to their pages trap (the rising `ic`).
- The only emulator change between 53c81b1a7a (clean, `3260817`) and fa56a26f1f (decays) is #504
  (a start-up GPU timestamp-period probe, vk/renderer.c) and #517 (vk/texture.c). surface.c is
  identical between them.

**This is on master.** fa56a26f1f and 09050ddbe5 are both ancestors of 85347ffbd1, and no later
fold resets `invalidation_frame` or adds a flush to that path (read, not measured: the master
arm below measures it). Every Forza race on a build since the #517 fold (2026-09-27 20:42 PDT)
should decay this way.

**The fix is emulator code, which this lane may not edit.** Two shapes, for the owner of
vk/surface.c: make "in flight" a submission count rather than a slot index (stamp
`r->submit_count` at invalidation, and treat the surface as in flight while fewer than
`num_active_frames` submissions have completed since), or reset `invalidation_frame` to -1 for
every surface stamped with a slot when that slot's fence is waited. Either keeps #517's saving.
Putting the flush back would undo #517.

## 4. The instrument: clocks in every thermal sample (blocked on #571)

`docs/testing/thermal_state.py` is in lane.fanduty507's PR #571, which is open (ready, not folded).
Per the brief, it is not edited before then. Board request:
`$DISPATCH_DIR/board-requests/forzadecay414.md` asks for the file after #571 folds. The fields:
per-policy `scaling_cur_freq` (policy0, 3, 7), whatever `scaling_max_freq` is readable, and the
kgsl `gpuclk` and `throttling`. Section 2 no longer needs it. It stays worth doing for the heat
track, because it is the one way to see LMh capping in any soak.

## 5. The discriminating runs

The brief's legs were Thor cold against Thor warm, plus the Nova. The cold-against-warm half is
answered by `3088454` against `1092424`/`1092523` (section 1): same code, 44.7 C against
58.5/61.7 C, the same curve. So no cold slot was asked of lane.local. What the data does not yet
show is the commit, on a device that never pauses. Registered before any device run (both files
at 2026-09-28T19:41:21Z), Nova, survey route, 360 s, perflog, max:

| file | A | B | legs |
|---|---|---|---|
| `forzadecay414-bisect.json` | f82e7e87fe (master before #517) | 09050ddbe5 (#517 fold) | M0 race reached; P0 A flushes (faf >= 0.2/flip), B does not (<= 0.02); P1 B's invalid >= 1000; P2 A's invalid <= 400; P3 fps t = 270-330 B/A <= 0.6 |
| `forzadecay414-master.json` | f82e7e87fe (same A run) | 85347ffbd1 (master) | M0; P1 master's invalid >= 1000; P3 B/A <= 0.6 |

Each leg's failing world is in the file. In short: P0 fails if A does not flush either, so the
flush is not the link. P1 fails if #517 alone does not leak on the Nova, so #518's pending
pre-download or the Thor is part of it. P2 fails if the leak predates #517. P3 fails if the list
costs the Nova no fps. The master legs fail if a later fold already stopped it. The three soaks
are 3 x (360 + 90) s = 22.5 min of device time, under the 30-min pilot line.

Queued 2026-09-28 ~12:43 PDT at release priority by `docs/lanes/forzadecay414/queue.sh`. Each
request's expect_sha was read back and matches its file (f7c4565c56dc bisect, ce4ca9775edd master):

| request | ref | role |
|---|---|---|
| `1-1790624588-forzadecay414-3394734` | f82e7e87fe | A of both |
| `1-1790624588-forzadecay414-3394828` | 09050ddbe5 | bisect B |
| `1-1790624589-forzadecay414-3394871` | 85347ffbd1 | master B |

**Waiting (session end, 2026-09-28 ~12:45 PDT)** on those three. The Nova is held by
battery-hostops (14% at 18:10Z, lifted at >= 80%), so they run after the owner's evening top-up.
On resume: judge both predictions by hand from the three logcats (timeline.py rows, `[watch311]
invalid=`, `txw` faf/scan), post the verdict on #414, and mark this PR ready. The instrument
(section 4) goes on its own branch once #571 folds and the board grants the file.

## Do not repeat

- Do not read the Thor's 2-4 fps step with audio starving as the decay. That is the xo-78 C pause
  (#507): it lands with `thermal-pause-F8`, and the vCPU and audio lose their cores.
- Do not look for H1 in core temperatures. The big cores sit at 94-96 C in runs that hold 18-24
  fps. Read `invalid=` on the `[watch311]` line first. If it climbs past a few hundred, the run
  is measuring the list, not the code under test. PR #543's hunk-5 pair (`1092424`/`1092523`)
  measured 9 fps in its window for that reason, against pilot 2's 17 on older code.
- Do not "fix" this by putting the flush back before direct binds. That undoes #517 for every
  title. The defect is the slot-index `invalidation_frame`.
